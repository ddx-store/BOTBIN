"""
Multi-source BIN data fetchers.
Three independent API handlers with unified output schema.
"""

import httpx
from bot.utils.logger import get_logger

logger = get_logger("bin_sources")

TIMEOUT = 6.0

_LEVEL_KW = [
    ("infinite privilege",  "INFINITE PRIVILEGE"),
    ("infinite",            "INFINITE"),
    ("centurion",           "CENTURION"),
    ("black",               "BLACK"),
    ("world elite",         "WORLD ELITE"),
    ("world",               "WORLD"),
    ("signature",           "SIGNATURE"),
    ("platinum",            "PLATINUM"),
    ("gold",                "GOLD"),
    ("business",            "BUSINESS"),
    ("corporate",           "CORPORATE"),
    ("commercial",          "COMMERCIAL"),
    ("prepaid",             "PREPAID"),
    ("classic",             "CLASSIC"),
    ("standard",            "STANDARD"),
    ("traditional",         "STANDARD"),
    ("electron",            "ELECTRON"),
]


def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return "\U0001f3f3\ufe0f"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _extract_level(*fields) -> str:
    combined = " ".join(f.lower() for f in fields if f)
    for kw, lvl in _LEVEL_KW:
        if kw in combined:
            return lvl
    return "CLASSIC"


def _normalize(d: dict, source: str) -> dict:
    return {
        "scheme":       (d.get("scheme")       or "N/A").upper(),
        "type":         (d.get("type")         or "N/A").upper(),
        "brand":        (d.get("brand")        or d.get("scheme") or "N/A").upper(),
        "level":        (d.get("level")        or "N/A").upper(),
        "bank":         (d.get("bank")         or "N/A"),
        "bank_city":    (d.get("bank_city")    or "N/A"),
        "bank_url":     (d.get("bank_url")     or "N/A"),
        "bank_phone":   (d.get("bank_phone")   or "N/A"),
        "country":      (d.get("country")      or "N/A"),
        "country_code": (d.get("country_code") or "N/A"),
        "currency":     (d.get("currency")     or "N/A"),
        "card_length":  str(d.get("card_length") or "16"),
        "emoji":        (d.get("emoji")        or _flag(d.get("country_code") or "")),
        "prepaid":      d.get("prepaid"),
        "source":       source,
    }


# ─── Source 1: binlist.net ────────────────────────────────────────────────────

async def fetch_binlist(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """Primary source — lookup.binlist.net. Most detailed (bank URL, phone, city, currency)."""
    try:
        resp = await client.get(
            f"https://lookup.binlist.net/{bin_key}",
            headers={"Accept-Version": "3"},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()

        scheme    = (data.get("scheme") or "").upper()
        brand_raw = (data.get("brand")  or scheme or "")
        typ       = (data.get("type")   or "N/A").upper()
        level     = _extract_level(brand_raw)

        bank_obj  = data.get("bank") or {}
        cntry     = data.get("country") or {}
        num_obj   = data.get("number") or {}
        cc        = (cntry.get("alpha2") or "N/A")

        return _normalize({
            "scheme":       scheme or "N/A",
            "type":         typ,
            "brand":        brand_raw.upper() or "N/A",
            "level":        level,
            "bank":         bank_obj.get("name") or "N/A",
            "bank_city":    bank_obj.get("city")  or "N/A",
            "bank_url":     bank_obj.get("url")   or "N/A",
            "bank_phone":   bank_obj.get("phone") or "N/A",
            "country":      cntry.get("name")     or "N/A",
            "country_code": cc,
            "currency":     cntry.get("currency") or "N/A",
            "card_length":  num_obj.get("length") or 16,
            "emoji":        cntry.get("emoji")    or _flag(cc),
            "prepaid":      data.get("prepaid"),
        }, source="binlist")
    except Exception as e:
        logger.debug(f"binlist {bin_key}: {e}")
        return None


# ─── Source 2: handyapi.com ───────────────────────────────────────────────────

async def fetch_handyapi(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """Secondary source — data.handyapi.com. Has CardTier field for level detection."""
    try:
        resp = await client.get(
            f"https://data.handyapi.com/bin/{bin_key}",
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if data.get("Status") != "SUCCESS":
            return None

        cntry      = data.get("Country") or {}
        card_tier  = data.get("CardTier") or ""
        scheme     = (data.get("Scheme") or "N/A").upper()
        cc         = (cntry.get("A2") or "N/A")

        return _normalize({
            "scheme":       scheme,
            "type":         (data.get("Type") or "N/A").upper(),
            "brand":        scheme,
            "level":        _extract_level(card_tier),
            "bank":         data.get("Issuer") or "N/A",
            "bank_phone":   cntry.get("ISD") or "N/A",
            "country":      cntry.get("Name") or "N/A",
            "country_code": cc,
            "emoji":        _flag(cc),
        }, source="handyapi")
    except Exception as e:
        logger.debug(f"handyapi {bin_key}: {e}")
        return None


# ─── Source 3: freebinlist.net ────────────────────────────────────────────────

async def fetch_freebinlist(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """Tertiary source — freebinlist.net. Has cardLevel field."""
    try:
        resp = await client.get(
            f"https://www.freebinlist.net/api/bin/{bin_key}",
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not data.get("isValid"):
            return None

        cc = (data.get("binCountryCode") or "N/A")
        return _normalize({
            "scheme":       (data.get("binScheme") or "N/A").upper(),
            "type":         (data.get("binType")   or "N/A").upper(),
            "level":        _extract_level(data.get("cardLevel") or ""),
            "bank":         data.get("bankName")    or "N/A",
            "country":      data.get("binCountryName") or "N/A",
            "country_code": cc,
            "emoji":        _flag(cc),
        }, source="freebinlist")
    except Exception as e:
        logger.debug(f"freebinlist {bin_key}: {e}")
        return None


# ─── Multi-source fetch ───────────────────────────────────────────────────────

async def fetch_bin_any(bin_key: str, client: httpx.AsyncClient) -> dict | None:
    """
    Try all three sources in priority order.
    Returns the first successful result.
    """
    for fetcher in (fetch_binlist, fetch_handyapi, fetch_freebinlist):
        result = await fetcher(bin_key, client)
        if result and result.get("scheme") not in ("N/A", "", None):
            return result
    return None
