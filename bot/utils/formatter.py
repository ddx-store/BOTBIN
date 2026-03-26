"""
Centralized message formatter for DDXSTORE bot.
All Telegram responses use HTML parse mode.
"""

import re

SEP = "\u2500" * 9          # ─────────  (short separator)
SEP_LONG = "\u2500" * 18   # longer separator for other commands
FOOT = "\u00a9 DDXSTORE \u2022 @ddx22"
ARROW = " \u21a0 "          # ↠


def _lv(label: str, value: str, emoji: str = "") -> str:
    em = (emoji + "  ") if emoji else "    "
    return em + "<b>" + label.ljust(8) + "</b>  \u00bb  " + value


def _trim(text: str, n: int = 20) -> str:
    t = (text or "N/A").strip()
    return (t[:n] + "\u2026") if len(t) > n else t


def _country_str(info: dict, upper: bool = False) -> str:
    c = info.get("country") or "\u2014"
    if upper:
        c = c.upper()
    e = info.get("emoji") or ""
    return (c + " " + e).strip()


def _code(val: str) -> str:
    return "<code>" + val + "</code>"


def _build_format(bin_input: str, fixed_month: str = None,
                  fixed_year: str = None, fixed_cvv: str = None) -> str:
    raw = (bin_input or "").strip()
    clean = re.sub(r"[^0-9xX]", "", raw)
    digit_part = re.sub(r"[xX].*", "", clean)
    x_part = clean[len(digit_part):]
    fmt = digit_part
    if x_part:
        fmt += x_part.lower()
    m = fixed_month or "x"
    y = fixed_year  or "x"
    c = fixed_cvv   or "xxx"
    return fmt + "|" + m + "|" + y + "|" + c


# ─── Card Generator ───────────────────────────────────────────────────────────

def gen_msg(user, prefix: str, info: dict, cards: list,
            bin_input: str = None, fixed_month: str = None,
            fixed_year: str = None, fixed_cvv: str = None,
            checked: int = None) -> str:

    uname = ("@" + user.username) if user.username else (user.first_name or str(user.id))

    brand = (info.get("scheme") or "N/A").upper()
    typ   = (info.get("type") or "N/A").upper()
    lvl   = (info.get("level") or "").upper()
    info_line = brand + " - " + typ + (" - " + lvl if lvl and lvl != "N/A" else "")

    bank    = (info.get("bank") or "N/A").upper()
    country = _country_str(info, upper=True)
    fmt_str = _build_format(bin_input or prefix, fixed_month, fixed_year, fixed_cvv)

    total = len(cards)
    passed = checked if checked is not None else total
    chk_line = "\u2022 <b>Checked</b>" + ARROW + str(passed) + "/" + str(total) + " \u2705"

    card_lines = [_code(c["number"] + "|" + c["month"] + "|" + c["year"] + "|" + c["cvv"]) + " \u2705"
                  for c in cards]

    parts = [
        "<b>DDXSTORE" + ARROW + "CC Generator</b>",
        SEP,
        "\u2022 <b>Bin</b>" + ARROW + "(" + prefix[:6] + ")",
        "\u2022 <b>Info</b>" + ARROW + info_line,
        "\u2022 <b>Bank</b>" + ARROW + bank,
        "\u2022 <b>Country</b>" + ARROW + country,
        "\u2022 <b>Format</b>" + ARROW + _code(fmt_str),
        chk_line,
        SEP,
        "",
    ] + card_lines + [
        "",
        SEP,
        "\u2022 <b>ReqBy</b>" + ARROW + uname,
        "\u2022 <b>DevBy</b>" + ARROW + "@ddx22",
    ]
    return "\n".join(parts)


def auto_gen_msg(user, prefix: str, info: dict, cards: list) -> str:
    return gen_msg(user, prefix, info, cards, bin_input=prefix)


# ─── BIN Lookup ──────────────────────────────────────────────────────────────

_SCHEME_ICON = {
    "VISA":       "\U0001f535",   # 🔵
    "MASTERCARD": "\U0001f7e0",   # 🟠
    "AMEX":       "\U0001f7e2",   # 🟢
    "DISCOVER":   "\U0001f7e1",   # 🟡
    "UNIONPAY":   "\U0001f534",   # 🔴
    "JCB":        "\u26aa",       # ⚪
    "DINERS":     "\U0001f7e3",   # 🟣
    "MAESTRO":    "\U0001f535",   # 🔵
}

_LEVEL_ICON = {
    "INFINITE PRIVILEGE": "\U0001f451",  # 👑
    "CENTURION":          "\U0001f451",  # 👑
    "BLACK":              "\u2b1b",      # ⬛
    "INFINITE":           "\u267e\ufe0f",# ♾
    "WORLD ELITE":        "\U0001f31f",  # 🌟
    "WORLD":              "\U0001f30e",  # 🌎
    "SIGNATURE":          "\u270d\ufe0f",# ✍
    "PLATINUM":           "\U0001fa69",  # 🪩 → use diamond
    "GOLD":               "\U0001f947",  # 🥇
    "BUSINESS":           "\U0001f4bc",  # 💼
    "CORPORATE":          "\U0001f4bc",  # 💼
    "COMMERCIAL":         "\U0001f4bc",  # 💼
    "CLASSIC":            "\U0001f4b3",  # 💳
    "STANDARD":           "\U0001f4b3",  # 💳
    "ELECTRON":           "\U0001f4b3",  # 💳
    "DEBIT":              "\U0001f4b3",  # 💳
    "PREPAID":            "\U0001f4b3",  # 💳
}


def _opt(label: str, val, emoji: str, trim: int = 30) -> str | None:
    v = (str(val) if val is not None else "").strip()
    if not v or v in ("N/A", "—", "none", "unknown"):
        return None
    return _lv(label, _trim(v, trim), emoji)


def bin_lookup_msg(bin_num: str, info: dict) -> str:
    scheme  = (info.get("scheme") or "N/A").upper()
    typ     = (info.get("type")   or "N/A").upper()
    level   = (info.get("level")  or "N/A").upper()
    prepaid = ("Yes ✅" if info.get("prepaid") is True
               else ("No 🚫" if info.get("prepaid") is False else "\u2014"))

    scheme_icon = _SCHEME_ICON.get(scheme, "\U0001f4b3")
    level_icon  = _LEVEL_ICON.get(level, "\u2b50")

    bank_name  = info.get("bank")       or ""
    bank_city  = info.get("bank_city")  or ""
    bank_url   = info.get("bank_url")   or ""
    bank_phone = info.get("bank_phone") or ""
    currency   = info.get("currency")   or ""
    c_len      = info.get("card_length") or ""

    country_str = _country_str(info)

    has_bank_extras = any(
        v and v not in ("N/A", "") for v in [bank_city, bank_url, bank_phone]
    )

    parts = [
        SEP_LONG,
        f"    {scheme_icon}  <b>DDX BIN LOOKUP</b>",
        SEP_LONG,
        _lv("BIN",     _code(bin_num[:6]), "\U0001f522"),
        "",
        _lv("Network", scheme,  "\U0001f310"),
        _lv("Type",    typ,     "\U0001f4cb"),
        _lv("Level",   f"{level_icon}  {level}", "\u2b50"),
        _lv("Prepaid", prepaid, "\U0001f4b0"),
    ]

    if c_len and c_len not in ("N/A", ""):
        parts.append(_lv("Length", f"{c_len} digits", "\U0001f4cf"))

    parts += [
        "",
        SEP_LONG,
        _lv("Bank",    _trim(bank_name, 30), "\U0001f3e6"),
        _lv("Country", country_str,          "\U0001f30d"),
    ]

    if currency and currency not in ("N/A", ""):
        parts.append(_lv("Currency", currency, "\U0001f4b1"))

    if has_bank_extras:
        parts.append("")
        if bank_city and bank_city not in ("N/A", ""):
            parts.append(_lv("City",    _trim(bank_city, 25),  "\U0001f4cd"))
        if bank_ph := _opt("Phone", bank_phone, "\U0001f4de", 20):
            parts.append(bank_ph)
        if bank_url and bank_url not in ("N/A", ""):
            url = bank_url if bank_url.startswith("http") else "https://" + bank_url
            parts.append(_lv("Website", f'<a href="{url}">{_trim(bank_url, 28)}</a>', "\U0001f517"))

    parts += [
        "",
        SEP_LONG,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Card Checker ─────────────────────────────────────────────────────────────

def chk_msg(card_number: str, valid: bool, info: dict,
            month: str = None, year: str = None, cvv: str = None,
            length_ok: bool = None,
            expiry_ok=None, expiry_note: str = None) -> str:

    overall_ok = valid and (length_ok is not False) and (expiry_ok is not False)
    header_icon = "\u2705" if overall_ok else "\u274c"
    status_text = ("<b>\u2705 VALID</b>" if overall_ok else "<b>\u274c INVALID</b>")
    luhn_text   = "Valid \u2714" if valid else "Invalid \u2718"

    masked = card_number[:6] + ("\u2022" * (len(card_number) - 10)) + card_number[-4:]

    full_card = card_number
    if month and year:
        full_card += f"|{month}|20{year}"
        if cvv:
            full_card += f"|{cvv}"

    parts = [
        SEP_LONG,
        "    " + header_icon + "  <b>DDX CARD CHECK</b>",
        SEP_LONG,
        _lv("Card", _code(masked), "\U0001f4b3"),
    ]

    if month and year:
        exp_str = f"{month}/20{year}" + (f" | CVV: {cvv}" if cvv else "")
        parts.append(_lv("Expiry", exp_str, "\U0001f4c5"))

    parts += [
        _lv("Status", status_text, "\U0001f50d"),
        _lv("Luhn",   luhn_text, "\U0001f510"),
    ]

    if length_ok is not None:
        parts.append(_lv("Length", f"{len(card_number)} \u2714" if length_ok else f"{len(card_number)} \u2718", "\U0001f4cf"))

    if expiry_note is not None:
        parts.append(_lv("Validity", expiry_note, "\u23f3"))

    parts += [
        _lv("Brand",   info.get("scheme") or "\u2014", "\U0001f3f7"),
        _lv("Type",    info.get("type") or "\u2014", "\U0001f4cb"),
        _lv("Level",   info.get("level") or "\u2014", "\u2b50"),
        _lv("Bank",    _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country_str(info), "\U0001f30d"),
        SEP_LONG,
        _lv("Full",    _code(full_card), "\U0001f4cb"),
        SEP_LONG,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Fake Identity ────────────────────────────────────────────────────────────

def fake_msg(fake: dict) -> str:
    ua = _trim(fake.get("useragent") or "\u2014", 35)
    parts = [
        SEP_LONG,
        "    \U0001f464  <b>DDX FAKE IDENTITY</b>",
        SEP_LONG,
        _lv("Name", fake.get("name") or "\u2014", "\U0001f9e5"),
        _lv("Email", _code(fake.get("email") or "\u2014"), "\U0001f4e7"),
        _lv("Pass", _code(fake.get("password") or "\u2014"), "\U0001f511"),
        _lv("DOB", fake.get("dob") or "\u2014", "\U0001f382"),
        _lv("SSN", _code(fake.get("ssn") or "\u2014"), "\U0001f4c4"),
        _lv("Phone", fake.get("phone") or "\u2014", "\u260e"),
        SEP_LONG,
        _lv("Country", fake.get("country") or "\u2014", "\U0001f30d"),
        _lv("City", fake.get("city") or "\u2014", "\U0001f3d9"),
        _lv("Street", fake.get("street") or "\u2014", "\U0001f6e3"),
        _lv("State", fake.get("state") or "\u2014", "\U0001f4cd"),
        _lv("ZIP", fake.get("zip") or "\u2014", "\U0001f4ee"),
        SEP_LONG,
        _lv("IP", _code(fake.get("ip") or "\u2014"), "\U0001f310"),
        _lv("UA", _code(ua), "\U0001f4bb"),
        SEP_LONG,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)
