"""
Centralized message formatter for DDXSTORE bot.
All Telegram responses use HTML parse mode.
"""

S = "\u2501" * 22
FOOT = "\u00a9 DDXSTORE \u2022 @ddx22"


def _lv(label: str, value: str, emoji: str = "") -> str:
    em = (emoji + "  ") if emoji else "    "
    return em + "<b>" + label.ljust(8) + "</b>  \u00bb  " + value


def _trim(text: str, n: int = 20) -> str:
    t = (text or "N/A").strip()
    return (t[:n] + "\u2026") if len(t) > n else t


def _country(info: dict) -> str:
    c = info.get("country") or "\u2014"
    e = info.get("emoji") or ""
    return (c + "  " + e).strip()


def _code(val: str) -> str:
    return "<code>" + val + "</code>"


# ─── BIN Lookup ──────────────────────────────────────────────────────────────

def bin_lookup_msg(bin_num: str, info: dict) -> str:
    prepaid = "Yes" if info.get("prepaid") is True else ("No" if info.get("prepaid") is False else "\u2014")
    level = _trim(info.get("level") or "\u2014", 22)
    parts = [
        S,
        "    \U0001f4b3  <b>DDX BIN LOOKUP</b>",
        S,
        _lv("BIN", _code(bin_num[:6]), "\U0001f522"),
        _lv("Brand", info.get("scheme") or "\u2014", "\U0001f3f7"),
        _lv("Type", info.get("type") or "\u2014", "\U0001f4cb"),
        _lv("Level", level, "\u2b50"),
        _lv("Bank", _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country(info), "\U0001f30d"),
        _lv("Prepaid", prepaid, "\U0001f4b0"),
        S,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Card Generator ───────────────────────────────────────────────────────────

def gen_msg(user, prefix: str, info: dict, cards: list, addr: dict = None) -> str:
    lines = [_code(c["number"] + "|" + c["month"] + "|" + c["year"] + "|" + c["cvv"]) for c in cards]
    uname = ("@" + user.username) if user.username else (user.first_name or str(user.id))
    brand_info = (info.get("scheme") or "\u2014") + "  \u00b7  " + (info.get("type") or "\u2014")

    parts = [
        S,
        "    \U0001f4b3  <b>DDX CC GENERATOR</b>",
        S,
        _lv("BIN", _code(prefix[:6]), "\U0001f522"),
        _lv("Brand", brand_info, "\U0001f3f7"),
        _lv("Bank", _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country(info), "\U0001f30d"),
        _lv("Count", str(len(cards)), "\U0001f4ca"),
    ]
    if addr:
        city = addr.get("city") or ""
        z = addr.get("zip") or ""
        parts.append(_lv("Addr", city + ", " + z, "\U0001f4cd"))
    parts += [S] + lines + [S, "    \U0001f464  <b>ReqBy</b>  \u00bb  " + uname, "    <i>" + FOOT + "</i>"]
    return "\n".join(parts)


# ─── Card Checker ─────────────────────────────────────────────────────────────

def chk_msg(card_number: str, valid: bool, info: dict) -> str:
    status_text = "<b>\u2705 VALID</b>" if valid else "<b>\u274c INVALID</b>"
    luhn_text = "Valid \u2714" if valid else "Invalid \u2718"
    header_icon = "\u2705" if valid else "\u274c"
    masked = card_number[:6] + ("\u2022" * (len(card_number) - 10)) + card_number[-4:]

    parts = [
        S,
        "    " + header_icon + "  <b>DDX CARD CHECK</b>",
        S,
        _lv("Card", _code(masked), "\U0001f4b3"),
        _lv("Status", status_text, "\U0001f50d"),
        _lv("Luhn", luhn_text, "\U0001f510"),
        _lv("Brand", info.get("scheme") or "\u2014", "\U0001f3f7"),
        _lv("Type", info.get("type") or "\u2014", "\U0001f4cb"),
        _lv("Bank", _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country(info), "\U0001f30d"),
        S,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Fake Identity ────────────────────────────────────────────────────────────

def fake_msg(fake: dict) -> str:
    ua = _trim(fake.get("useragent") or "\u2014", 35)
    parts = [
        S,
        "    \U0001f464  <b>DDX FAKE IDENTITY</b>",
        S,
        _lv("Name", fake.get("name") or "\u2014", "\U0001f9e5"),
        _lv("Email", _code(fake.get("email") or "\u2014"), "\U0001f4e7"),
        _lv("Pass", _code(fake.get("password") or "\u2014"), "\U0001f511"),
        _lv("DOB", fake.get("dob") or "\u2014", "\U0001f382"),
        _lv("SSN", _code(fake.get("ssn") or "\u2014"), "\U0001f4c4"),
        _lv("Phone", fake.get("phone") or "\u2014", "\u260e"),
        S,
        _lv("Country", fake.get("country") or "\u2014", "\U0001f30d"),
        _lv("City", fake.get("city") or "\u2014", "\U0001f3d9"),
        _lv("Street", fake.get("street") or "\u2014", "\U0001f6e3"),
        _lv("State", fake.get("state") or "\u2014", "\U0001f4cd"),
        _lv("ZIP", fake.get("zip") or "\u2014", "\U0001f4ee"),
        S,
        _lv("IP", _code(fake.get("ip") or "\u2014"), "\U0001f310"),
        _lv("UA", _code(ua), "\U0001f4bb"),
        S,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Auto BIN (router) ────────────────────────────────────────────────────────

def auto_gen_msg(user, prefix: str, info: dict, cards: list) -> str:
    lines = [_code(c["number"] + "|" + c["month"] + "|" + c["year"] + "|" + c["cvv"]) for c in cards]
    uname = ("@" + user.username) if user.username else (user.first_name or str(user.id))
    parts = [
        S,
        "    \u26a1  <b>DDX AUTO GEN</b>",
        S,
        _lv("BIN", _code(prefix[:6]), "\U0001f522"),
        _lv("Brand", info.get("scheme") or "\u2014", "\U0001f3f7"),
        _lv("Bank", _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country(info), "\U0001f30d"),
        S,
    ] + lines + [S, "    \U0001f464  <b>ReqBy</b>  \u00bb  " + uname, "    <i>" + FOOT + "</i>"]
    return "\n".join(parts)
