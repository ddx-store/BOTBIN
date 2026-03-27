"""
Centralized message formatter for DDXSTORE bot.
All Telegram responses use HTML parse mode.
"""

import re
import html as _html

SEP = "\u2500" * 9          # ─────────  (short separator)
SEP_LONG = "\u2500" * 18   # longer separator for other commands
FOOT = "\u00a9 DDXSTORE \u2022 @ddx22"
ARROW = " \u21a0 "          # ↠


def _e(s) -> str:
    """HTML-escape a raw value from external sources or user input."""
    return _html.escape(str(s) if s is not None else "")


def _lv(label: str, value: str, emoji: str = "") -> str:
    em = (emoji + "  ") if emoji else "    "
    return em + "<b>" + label.ljust(8) + "</b>  \u00bb  " + value


def _trim(text: str, n: int = 20) -> str:
    t = _e((text or "N/A").strip())
    return (t[:n] + "\u2026") if len(t) > n else t


def _country_str(info: dict, upper: bool = False) -> str:
    c = info.get("country") or "\u2014"
    if upper:
        c = c.upper()
    e = info.get("emoji") or ""
    return (_e(c) + " " + e).strip()


def _code(val: str) -> str:
    return "<code>" + _e(val) + "</code>"


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

    uname = _e(("@" + user.username) if user.username else (user.first_name or str(user.id)))

    brand = _e((info.get("scheme") or "N/A").upper())
    typ   = _e((info.get("type") or "N/A").upper())
    lvl   = _e((info.get("level") or "").upper())
    info_line = brand + " - " + typ + (" - " + lvl if lvl and lvl != "N/A" else "")

    bank    = _e((info.get("bank") or "N/A").upper())
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
    scheme  = _e((info.get("scheme") or "N/A").upper())
    typ     = _e((info.get("type")   or "N/A").upper())
    level   = _e((info.get("level")  or "N/A").upper())
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

    region = (info.get("issued_region") or "").strip()

    parts += [
        "",
        SEP_LONG,
        _lv("Bank",    _trim(bank_name, 30), "\U0001f3e6"),
        _lv("Country", country_str,          "\U0001f30d"),
    ]

    if region and region not in ("N/A", ""):
        parts.append(_lv("Region", _e(region), "\U0001f5fa\ufe0f"))

    if currency and currency not in ("N/A", ""):
        parts.append(_lv("Currency", _e(currency), "\U0001f4b1"))

    if has_bank_extras:
        parts.append("")
        if bank_city and bank_city not in ("N/A", ""):
            parts.append(_lv("City",    _trim(bank_city, 25),  "\U0001f4cd"))
        if bank_ph := _opt("Phone", bank_phone, "\U0001f4de", 20):
            parts.append(bank_ph)
        if bank_url and bank_url not in ("N/A", ""):
            raw_url = bank_url if bank_url.startswith("http") else "https://" + bank_url
            safe_href = _html.escape(raw_url, quote=True)
            parts.append(_lv("Website", f'<a href="{safe_href}">{_trim(bank_url, 28)}</a>', "\U0001f517"))

    parts += [
        "",
        SEP_LONG,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Card Checker ─────────────────────────────────────────────────────────────

_LIVE_ICON = {
    "live":          "\u2705",
    "dead":          "\u274c",
    "insufficient":  "\u26a0\ufe0f",
    "ccv_error":     "\u274c",
    "3d_secure":     "\U0001f512",
    "error":         "\u26a0\ufe0f",
    "rate_limited":  "\u23f3",
    "unknown":       "\u2753",
}


def chk_msg(card_number: str, valid: bool, info: dict,
            month: str = None, year: str = None, cvv: str = None,
            length_ok: bool = None,
            expiry_ok=None, expiry_note: str = None,
            live_result: dict = None) -> str:

    overall_ok = valid and (length_ok is not False) and (expiry_ok is not False)
    if live_result and live_result.get("status") in ("dead", "ccv_error"):
        overall_ok = False
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

    if live_result:
        icon = _LIVE_ICON.get(live_result.get("status", ""), "\u2753")
        parts += [
            "",
            SEP_LONG,
            "    \U0001f4e1  <b>LIVE CHECK</b>",
            SEP_LONG,
            _lv("Result", f"{icon} {_e(live_result.get('display', '—'))}", "\U0001f4e1"),
            _lv("Gate",   _e(live_result.get("gate", "—")), "\U0001f310"),
        ]
        raw_msg = live_result.get("raw_message", "")
        if raw_msg:
            parts.append(_lv("Detail", _trim(raw_msg, 40), "\U0001f4ac"))

    chk_region = (info.get("issued_region") or "").strip()
    parts += [
        "",
        _lv("Brand",   _e(info.get("scheme") or "\u2014"), "\U0001f3f7"),
        _lv("Type",    _e(info.get("type") or "\u2014"), "\U0001f4cb"),
        _lv("Level",   _e(info.get("level") or "\u2014"), "\u2b50"),
        _lv("Bank",    _trim(info.get("bank") or "\u2014", 28), "\U0001f3e6"),
        _lv("Country", _country_str(info), "\U0001f30d"),
    ]
    if chk_region and chk_region not in ("N/A", ""):
        parts.append(_lv("Region", _e(chk_region), "\U0001f5fa\ufe0f"))
    parts += [
        SEP_LONG,
        _lv("Full",    _code(full_card), "\U0001f4cb"),
        SEP_LONG,
        "    <i>" + FOOT + "</i>",
    ]
    return "\n".join(parts)


# ─── Fake Identity ────────────────────────────────────────────────────────────

_FAKE_SEP = "\u2501" * 14   # ━━━━━━━━━━━━━━

def fake_msg(fake: dict) -> str:
    country   = (fake.get("country") or "").upper()
    flag      = fake.get("flag") or ""
    name      = _e(fake.get("name") or "\u2014")
    gender    = _e(fake.get("gender") or "\u2014")
    street    = _e(fake.get("street") or "\u2014")
    city      = _e(fake.get("city") or "\u2014")
    state     = _e(fake.get("state") or "\u2014")
    zipcode   = _e(fake.get("zip") or "\u2014")
    phone     = _e(fake.get("phone") or "\u2014")
    email     = _e(fake.get("email") or "\u2014")
    password  = _e(fake.get("password") or "\u2014")
    dob       = _e(fake.get("dob") or "\u2014")
    ssn       = _e(fake.get("ssn") or "\u2014")
    ip        = _e(fake.get("ip") or "\u2014")

    lines = [
        f"\U0001f4cd {_e(country)} \u2014 Fake Identity {flag}",
        _FAKE_SEP,
        f"\U0001f194 Full Name: <code>{name}</code>",
        f"\U0001f464 Gender: {gender}",
        f"\U0001f3e0 Street Address: <code>{street}</code>",
        f"\U0001f3d9\ufe0f City/Town: <code>{city}</code>",
        f"\U0001f5fa\ufe0f State/Region: <code>{state}</code>",
        f"\U0001f4ee Postal Code: <code>{zipcode}</code>",
        f"\U0001f4de Phone Number: <code>{phone}</code>",
        f"\U0001f4e7 Email: <code>{email}</code>",
        f"\U0001f511 Password: <code>{password}</code>",
        f"\U0001f382 Date of Birth: <code>{dob}</code>",
        f"\U0001f4c4 SSN: <code>{ssn}</code>",
        f"\U0001f310 IP Address: <code>{ip}</code>",
        f"\U0001f30d Country: {_e(country)} {flag}",
        _FAKE_SEP,
    ]
    return "\n".join(lines)
