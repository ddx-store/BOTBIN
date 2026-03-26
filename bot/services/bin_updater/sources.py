"""
Multi-source BIN data fetchers — production-grade.

Sources (priority order):
  1. binlist.net   — most detailed (bank URL/phone/city/currency)
  2. handyapi.com  — reliable, CardTier level detection
  3. bintable.com  — last-resort fallback, free tier

Features:
  - Per-source circuit breaker: opens after N consecutive failures,
    resets after CIRCUIT_RESET_S seconds — stops hammering dead endpoints
  - Rotating User-Agent pool to avoid trivial bot detection
  - Graduated timeouts: fast first attempt, slower on fallback
  - Unified output schema across all sources
  - 429 rate-limit detection with per-source backoff hint
"""

import time
import random
import httpx
from bot.utils.logger import get_logger

logger = get_logger("bin_sources")

TIMEOUT_FAST = 4.0    # first-attempt timeout
TIMEOUT_SLOW = 8.0    # fallback / retry timeout

# ─── Circuit breaker ──────────────────────────────────────────────────────────
# Per-source state: tracks consecutive failures and opens the circuit for
# CIRCUIT_RESET_S seconds when CIRCUIT_THRESHOLD failures accumulate.

CIRCUIT_THRESHOLD = 6    # failures before opening
CIRCUIT_RESET_S   = 90   # seconds circuit stays open before half-open retry

_CIRCUIT: dict[str, dict] = {
    "binlist":  {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0},
    "handyapi": {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0},
    "bintable": {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0},
}


def circuit_ok(source: str) -> bool:
    now   = time.monotonic()
    state = _CIRCUIT.get(source, {})
    if state.get("open_until", 0) > now:
        return False
    if state.get("rate_limited_until", 0) > now:
        return False
    return True


def circuit_success(source: str) -> None:
    state = _CIRCUIT.setdefault(source, {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0})
    state["failures"]    = 0
    state["open_until"]  = 0.0


def circuit_failure(source: str) -> None:
    state = _CIRCUIT.setdefault(source, {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0})
    state["failures"] += 1
    if state["failures"] >= CIRCUIT_THRESHOLD:
        state["open_until"] = time.monotonic() + CIRCUIT_RESET_S
        state["failures"]   = 0
        logger.warning(f"Circuit OPEN for '{source}' — cooling {CIRCUIT_RESET_S}s")


def circuit_rate_limit(source: str, retry_after: int = 60) -> None:
    """Called on HTTP 429. Backs off the source for retry_after seconds."""
    state = _CIRCUIT.setdefault(source, {"failures": 0, "open_until": 0.0, "rate_limited_until": 0.0})
    state["rate_limited_until"] = time.monotonic() + retry_after
    logger.warning(f"Rate limited on '{source}' — pausing {retry_after}s")


def get_circuit_status() -> dict:
    """Return human-readable circuit status for admin reporting."""
    now = time.monotonic()
    out = {}
    for src, state in _CIRCUIT.items():
        if state["open_until"] > now:
            out[src] = f"OPEN ({int(state['open_until'] - now)}s remaining)"
        elif state["rate_limited_until"] > now:
            out[src] = f"RATE_LIMITED ({int(state['rate_limited_until'] - now)}s remaining)"
        else:
            out[src] = f"CLOSED (failures={state['failures']})"
    return out


# ─── User-Agent pool ──────────────────────────────────────────────────────────

_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
]


def _ua() -> str:
    return random.choice(_USER_AGENTS)


def _base_headers() -> dict:
    return {
        "User-Agent":      _ua(),
        "Accept":          "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection":      "keep-alive",
    }


# ─── Level extraction ─────────────────────────────────────────────────────────

_LEVEL_KW = [
    ("infinite privilege", "INFINITE PRIVILEGE"),
    ("infinite",           "INFINITE"),
    ("centurion",          "CENTURION"),
    ("black",              "BLACK"),
    ("world elite",        "WORLD ELITE"),
    ("world",              "WORLD"),
    ("signature",          "SIGNATURE"),
    ("platinum",           "PLATINUM"),
    ("gold",               "GOLD"),
    ("business",           "BUSINESS"),
    ("corporate",          "CORPORATE"),
    ("commercial",         "COMMERCIAL"),
    ("prepaid",            "PREPAID"),
    ("classic",            "CLASSIC"),
    ("standard",           "STANDARD"),
    ("traditional",        "STANDARD"),
    ("electron",           "ELECTRON"),
]


def _extract_level(*fields: str) -> str:
    combined = " ".join(f.lower() for f in fields if f)
    for kw, lvl in _LEVEL_KW:
        if kw in combined:
            return lvl
    return "CLASSIC"


# ─── Flag helper ──────────────────────────────────────────────────────────────

def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return "\U0001f3f3\ufe0f"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


# ─── Normalized output schema ─────────────────────────────────────────────────

def _normalize(d: dict, source: str) -> dict:
    cc = (d.get("country_code") or "N/A").upper()
    return {
        "scheme":       (d.get("scheme")       or "N/A").upper(),
        "type":         (d.get("type")         or "N/A").upper(),
        "brand":        (d.get("brand") or d.get("scheme") or "N/A").upper(),
        "level":        (d.get("level")        or "N/A").upper(),
        "bank":         (d.get("bank")         or "N/A"),
        "bank_city":    (d.get("bank_city")    or "N/A"),
        "bank_url":     (d.get("bank_url")     or "N/A"),
        "bank_phone":   (d.get("bank_phone")   or "N/A"),
        "country":      (d.get("country")      or "N/A"),
        "country_code": cc,
        "currency":     (d.get("currency")     or "N/A"),
        "card_length":  str(d.get("card_length") or "16"),
        "emoji":        (d.get("emoji")        or _flag(cc)),
        "prepaid":      d.get("prepaid"),
        "source":       source,
    }


# ─── Source 1: binlist.net ────────────────────────────────────────────────────

async def fetch_binlist(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """
    Primary source — lookup.binlist.net
    Most detailed: bank city, URL, phone, currency, card length.
    Rate limited ~10 req/s without API key; circuit breaker protects against 429 storms.
    """
    if not circuit_ok("binlist"):
        return None

    try:
        resp = await client.get(
            f"https://lookup.binlist.net/{bin_key}",
            headers={**_base_headers(), "Accept-Version": "3"},
            timeout=TIMEOUT_FAST,
        )

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 60))
            circuit_rate_limit("binlist", retry_after)
            return None

        if resp.status_code == 404:
            circuit_success("binlist")   # valid response, BIN just unknown
            return None

        if resp.status_code != 200:
            circuit_failure("binlist")
            return None

        data      = resp.json()
        scheme    = (data.get("scheme") or "").upper()
        brand_raw = (data.get("brand")  or scheme or "")
        typ       = (data.get("type")   or "N/A").upper()
        level     = _extract_level(brand_raw)
        bank_obj  = data.get("bank")    or {}
        cntry     = data.get("country") or {}
        num_obj   = data.get("number")  or {}
        cc        = (cntry.get("alpha2") or "N/A")

        result = _normalize({
            "scheme":       scheme or "N/A",
            "type":         typ,
            "brand":        brand_raw.upper() or "N/A",
            "level":        level,
            "bank":         bank_obj.get("name")  or "N/A",
            "bank_city":    bank_obj.get("city")   or "N/A",
            "bank_url":     bank_obj.get("url")    or "N/A",
            "bank_phone":   bank_obj.get("phone")  or "N/A",
            "country":      cntry.get("name")      or "N/A",
            "country_code": cc,
            "currency":     cntry.get("currency")  or "N/A",
            "card_length":  num_obj.get("length")  or 16,
            "emoji":        cntry.get("emoji")     or _flag(cc),
            "prepaid":      data.get("prepaid"),
        }, source="binlist")

        circuit_success("binlist")
        return result

    except (httpx.TimeoutException, httpx.ConnectError) as e:
        circuit_failure("binlist")
        logger.debug(f"binlist {bin_key}: {type(e).__name__}")
        return None
    except Exception as e:
        circuit_failure("binlist")
        logger.debug(f"binlist {bin_key}: {e}")
        return None


# ─── Source 2: handyapi.com ───────────────────────────────────────────────────

async def fetch_handyapi(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """
    Secondary source — data.handyapi.com
    Reliable fallback; provides CardTier for accurate level detection.
    """
    if not circuit_ok("handyapi"):
        return None

    try:
        resp = await client.get(
            f"https://data.handyapi.com/bin/{bin_key}",
            headers=_base_headers(),
            timeout=TIMEOUT_FAST,
        )

        if resp.status_code == 429:
            circuit_rate_limit("handyapi", 45)
            return None

        if resp.status_code == 404:
            circuit_success("handyapi")
            return None

        if resp.status_code != 200:
            circuit_failure("handyapi")
            return None

        data = resp.json()
        if data.get("Status") != "SUCCESS":
            circuit_success("handyapi")   # API responded but BIN unknown
            return None

        cntry     = data.get("Country") or {}
        card_tier = data.get("CardTier") or ""
        scheme    = (data.get("Scheme") or "N/A").upper()
        cc        = (cntry.get("A2") or "N/A")

        result = _normalize({
            "scheme":       scheme,
            "type":         (data.get("Type") or "N/A").upper(),
            "brand":        scheme,
            "level":        _extract_level(card_tier, scheme),
            "bank":         data.get("Issuer")       or "N/A",
            "bank_phone":   cntry.get("ISD")         or "N/A",
            "country":      cntry.get("Name")        or "N/A",
            "country_code": cc,
            "emoji":        _flag(cc),
        }, source="handyapi")

        circuit_success("handyapi")
        return result

    except (httpx.TimeoutException, httpx.ConnectError) as e:
        circuit_failure("handyapi")
        logger.debug(f"handyapi {bin_key}: {type(e).__name__}")
        return None
    except Exception as e:
        circuit_failure("handyapi")
        logger.debug(f"handyapi {bin_key}: {e}")
        return None


# ─── Source 3: bintable.com ───────────────────────────────────────────────────

async def fetch_bintable(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """
    Last-resort fallback — bintable.com free tier.
    Slower, less detailed, but independent infrastructure from sources 1 & 2.
    """
    if not circuit_ok("bintable"):
        return None

    try:
        resp = await client.get(
            f"https://api.bintable.com/v1/{bin_key}",
            headers=_base_headers(),
            timeout=TIMEOUT_SLOW,
        )

        if resp.status_code == 429:
            circuit_rate_limit("bintable", 120)
            return None

        if resp.status_code == 404:
            circuit_success("bintable")
            return None

        if resp.status_code != 200:
            circuit_failure("bintable")
            return None

        data   = resp.json()
        result_data = data.get("data") or data   # response varies by version

        if not result_data or result_data.get("response_code") == "1":
            circuit_success("bintable")
            return None

        cc     = (result_data.get("country_code") or
                  (result_data.get("country") or {}).get("alpha2") or "N/A")
        scheme = (result_data.get("scheme") or "N/A").upper()
        bank   = (result_data.get("bank")   or
                  result_data.get("issuer") or "N/A")

        result = _normalize({
            "scheme":       scheme,
            "type":         (result_data.get("type") or "N/A").upper(),
            "brand":        scheme,
            "level":        _extract_level(result_data.get("card_tier") or "",
                                           result_data.get("brand") or ""),
            "bank":         bank if isinstance(bank, str) else (bank.get("name") or "N/A"),
            "country":      (result_data.get("country_name") or
                             (result_data.get("country") or {}).get("name") or "N/A"),
            "country_code": cc,
            "emoji":        _flag(cc),
            "prepaid":      result_data.get("prepaid"),
        }, source="bintable")

        circuit_success("bintable")
        return result

    except (httpx.TimeoutException, httpx.ConnectError) as e:
        circuit_failure("bintable")
        logger.debug(f"bintable {bin_key}: {type(e).__name__}")
        return None
    except Exception as e:
        circuit_failure("bintable")
        logger.debug(f"bintable {bin_key}: {e}")
        return None


# ─── Multi-source fetch ───────────────────────────────────────────────────────

async def fetch_bin_any(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """
    Try all sources in priority order.
    A result is accepted only when it has a valid (non-N/A) scheme.
    Circuit breakers skip dead sources instantly without waiting for timeouts.
    """
    for fetcher in (fetch_binlist, fetch_handyapi, fetch_bintable):
        result = await fetcher(bin_key, client)
        if result and result.get("scheme") not in ("N/A", "", None):
            return result
    return None
