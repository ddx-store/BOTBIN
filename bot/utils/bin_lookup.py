"""
Multi-source BIN lookup with:
  1. Memory cache (instant)
  2. Local SQLite DB (fast)
  3. binlist.net API (primary, most detailed)
  4. handyapi.com API (fallback, has CardTier)
  5. Range-based detection (last resort)
"""

import httpx
from bot.config.settings import BIN_LOOKUP_URL, BIN_LOOKUP_URL2, BIN_LOOKUP_TIMEOUT
from bot.utils.cache import bin_cache
from bot.database.bin_db import get_bin_local, save_bin_local
from bot.utils.logger import get_logger

logger = get_logger("bin_lookup")

_EMPTY = {
    "scheme":       "N/A",
    "type":         "N/A",
    "brand":        "N/A",
    "level":        "N/A",
    "bank":         "N/A",
    "bank_city":    "N/A",
    "bank_url":     "N/A",
    "bank_phone":   "N/A",
    "country":      "N/A",
    "country_code": "N/A",
    "currency":     "N/A",
    "card_length":  "N/A",
    "emoji":        "\U0001f3f3\ufe0f",
    "prepaid":      None,
    "source":       "none",
}

_LEVEL_KEYWORDS = [
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
    ("debit",               "DEBIT"),
]

_SCHEME_ICON = {
    "VISA":       "💳 VISA",
    "MASTERCARD": "💳 MASTERCARD",
    "AMEX":       "💳 AMEX",
    "DISCOVER":   "💳 DISCOVER",
    "JCB":        "💳 JCB",
    "UNIONPAY":   "💳 UNIONPAY",
    "DINERS":     "💳 DINERS",
    "MAESTRO":    "💳 MAESTRO",
    "INTERAC":    "💳 INTERAC",
}

_RANGE_DETECT = [
    ("34",   "AMEX",       "CREDIT",  "GOLD",     15),
    ("37",   "AMEX",       "CREDIT",  "GOLD",     15),
    ("300",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("301",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("302",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("303",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("304",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("305",  "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("36",   "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("38",   "DINERS",     "CREDIT",  "CLASSIC",  14),
    ("3528", "JCB",        "CREDIT",  "CLASSIC",  16),
    ("3529", "JCB",        "CREDIT",  "CLASSIC",  16),
    ("353",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("354",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("355",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("356",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("357",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("358",  "JCB",        "CREDIT",  "CLASSIC",  16),
    ("4",    "VISA",       "DEBIT",   "CLASSIC",  16),
    ("51",   "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("52",   "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("53",   "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("54",   "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("55",   "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("2221", "MASTERCARD", "CREDIT",  "STANDARD", 16),
    ("2720", "MASTERCARD", "CREDIT",  "WORLD",    16),
    ("62",   "UNIONPAY",   "CREDIT",  "STANDARD", 16),
    ("6011", "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("644",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("645",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("646",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("647",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("648",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("649",  "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("65",   "DISCOVER",   "CREDIT",  "CLASSIC",  16),
    ("6304", "MAESTRO",    "DEBIT",   "STANDARD", 18),
    ("6759", "MAESTRO",    "DEBIT",   "STANDARD", 16),
    ("6761", "MAESTRO",    "DEBIT",   "STANDARD", 16),
    ("6762", "MAESTRO",    "DEBIT",   "STANDARD", 16),
    ("6763", "MAESTRO",    "DEBIT",   "STANDARD", 16),
]


def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return "\U0001f3f3\ufe0f"
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _extract_level(brand: str, card_tier: str = None) -> str:
    src = ((card_tier or "") + " " + (brand or "")).lower().strip()
    for keyword, level in _LEVEL_KEYWORDS:
        if keyword in src:
            return level
    return "CLASSIC"


def _range_detect(bin_number: str) -> dict | None:
    key = bin_number[:6]
    for prefix, scheme, typ, level, length in _RANGE_DETECT:
        if key.startswith(prefix):
            result = dict(_EMPTY)
            result.update({
                "scheme": scheme,
                "type":   typ,
                "brand":  scheme,
                "level":  level,
                "card_length": str(length),
                "source": "range",
            })
            return result
    return None


def _parse_binlist(data: dict, key: str) -> dict:
    scheme    = (data.get("scheme") or "").upper() or "N/A"
    brand_raw = (data.get("brand")  or scheme)
    typ       = (data.get("type")   or "N/A").upper()
    brand     = (brand_raw or "N/A").upper()
    level     = _extract_level(brand_raw)

    bank_obj  = data.get("bank") or {}
    bank_name = (bank_obj.get("name") or "N/A")
    bank_city = (bank_obj.get("city") or "N/A")
    bank_url  = (bank_obj.get("url")  or "N/A")
    bank_ph   = (bank_obj.get("phone") or "N/A")

    cntry = data.get("country") or {}
    country_name = (cntry.get("name") or "N/A")
    country_code = (cntry.get("alpha2") or "N/A")
    currency     = (cntry.get("currency") or "N/A")
    emoji        = (cntry.get("emoji") or _flag(country_code))

    num_obj  = data.get("number") or {}
    c_length = str(num_obj.get("length") or "N/A")

    return {
        "scheme":       scheme,
        "type":         typ,
        "brand":        brand,
        "level":        level,
        "bank":         bank_name,
        "bank_city":    bank_city,
        "bank_url":     bank_url,
        "bank_phone":   bank_ph,
        "country":      country_name,
        "country_code": country_code,
        "currency":     currency,
        "card_length":  c_length,
        "emoji":        emoji,
        "prepaid":      data.get("prepaid"),
        "source":       "binlist",
    }


def _parse_handyapi(data: dict, key: str) -> dict:
    scheme     = (data.get("Scheme") or "").upper() or "N/A"
    typ        = (data.get("Type")   or "N/A").upper()
    issuer     = (data.get("Issuer") or "N/A")
    card_tier  = (data.get("CardTier") or "")
    level      = _extract_level(card_tier, card_tier)

    cntry = data.get("Country") or {}
    country_code = (cntry.get("A2") or "N/A")
    country_name = (cntry.get("Name") or "N/A")
    isd          = (cntry.get("ISD") or "N/A")

    return {
        "scheme":       scheme,
        "type":         typ,
        "brand":        scheme,
        "level":        level,
        "bank":         issuer,
        "bank_city":    "N/A",
        "bank_url":     "N/A",
        "bank_phone":   isd if isd != "N/A" else "N/A",
        "country":      country_name,
        "country_code": country_code,
        "currency":     "N/A",
        "card_length":  "16",
        "emoji":        _flag(country_code),
        "prepaid":      None,
        "source":       "handyapi",
    }


async def bin_lookup(bin_number: str) -> dict:
    key = bin_number[:6]

    cached = bin_cache.get(key)
    if cached:
        logger.info(f"BIN {key} → memory cache")
        return cached

    local = get_bin_local(key)
    if local:
        bin_cache.set(key, local)
        logger.info(f"BIN {key} → local DB")
        return local

    async with httpx.AsyncClient(timeout=BIN_LOOKUP_TIMEOUT) as client:
        result = await _try_binlist(client, key)
        if not result:
            result = await _try_handyapi(client, key)

    if not result:
        result = _range_detect(key)
        if result:
            logger.info(f"BIN {key} → range detection")

    if not result:
        result = dict(_EMPTY)
        result["source"] = "unknown"

    bin_cache.set(key, result)
    if result.get("source") not in ("range", "unknown", "none"):
        save_bin_local(key, result)
        logger.info(f"BIN {key} → saved to local DB (source={result['source']})")

    return result


async def _try_binlist(client: httpx.AsyncClient, key: str) -> dict | None:
    try:
        resp = await client.get(
            f"{BIN_LOOKUP_URL}/{key}",
            headers={"Accept-Version": "3"},
        )
        if resp.status_code == 200:
            data = resp.json()
            result = _parse_binlist(data, key)
            logger.info(f"BIN {key} → binlist.net OK")
            return result
        logger.warning(f"BIN {key} → binlist.net HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"BIN {key} → binlist.net error: {e}")
    return None


async def _try_handyapi(client: httpx.AsyncClient, key: str) -> dict | None:
    try:
        resp = await client.get(f"{BIN_LOOKUP_URL2}/{key}")
        if resp.status_code == 200:
            data = resp.json()
            if data.get("Status") == "SUCCESS":
                result = _parse_handyapi(data, key)
                logger.info(f"BIN {key} → handyapi OK")
                return result
        logger.warning(f"BIN {key} → handyapi HTTP {resp.status_code}")
    except Exception as e:
        logger.warning(f"BIN {key} → handyapi error: {e}")
    return None
