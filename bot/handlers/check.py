import re
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.luhn import is_valid_luhn
from bot.utils.bin_lookup import bin_lookup
from bot.utils.formatter import chk_msg
from bot.services.i18n import (
    MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD,
    MSG_CHK_EXAMPLE, MSG_CHK_CHECKING, MSG_ERROR,
)
from bot.utils.logger import get_logger

logger = get_logger("check")

CARD_LENGTHS = {
    "visa":       [13, 16, 19],
    "mastercard": [16],
    "amex":       [15],
    "discover":   [16, 19],
    "unionpay":   [16, 17, 18, 19],
    "maestro":    [12, 13, 14, 15, 16, 17, 18, 19],
    "jcb":        [16, 17, 18, 19],
    "dinersclub": [14],
}


def _parse_card_input(raw: str):
    parts = re.split(r"[|\s/\-]+", raw.strip())
    number = re.sub(r"[^0-9]", "", parts[0]) if parts else ""
    month  = parts[1].zfill(2) if len(parts) > 1 and parts[1].isdigit() else None
    year   = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
    cvv    = parts[3] if len(parts) > 3 and parts[3].isdigit() else None
    if year and len(year) == 4:
        year = year[2:]
    return number, month, year, cvv


def _check_expiry(month: str, year: str):
    try:
        m = int(month)
        y = int(year)
        if y < 100:
            y += 2000
        if not (1 <= m <= 12):
            return False, "شهر غير صحيح"
        now = datetime.now()
        if y < now.year or (y == now.year and m < now.month):
            return False, "منتهية الصلاحية ❌"
        months_left = (y - now.year) * 12 + (m - now.month)
        return True, f"صالحة — {months_left} شهر متبقي ✅"
    except Exception:
        return False, "تاريخ غير صحيح"


def _check_length(number: str, scheme: str) -> bool:
    scheme_key = (scheme or "").lower().replace(" ", "")
    expected = CARD_LENGTHS.get(scheme_key)
    if expected:
        return len(number) in expected
    return 13 <= len(number) <= 19


async def chk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    if not user:
        return

    if is_user_banned(user.id):
        await update.message.reply_text(MSG_BANNED)
        return
    if check_flood(user.id):
        await update.message.reply_text(MSG_FLOOD)
        return
    if not check_rate_limit(user.id):
        await update.message.reply_text(MSG_RATE_LIMIT)
        return

    text = update.message.text or ""
    match = re.match(r"^/(?:chk|check)(@\w+)?\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    raw_input = match.group(2).strip() if match else ""

    card_number, month, year, cvv = _parse_card_input(raw_input)

    if not card_number or len(card_number) < 13 or len(card_number) > 19:
        await update.message.reply_text(MSG_CHK_EXAMPLE)
        return

    increment_request_count(user.id)
    increment_request_stat()
    log_request(user.id, "chk", card_number[:6])
    logger.info(f"User {user.id} /chk BIN={card_number[:6]}")

    wait_msg = await update.message.reply_text(MSG_CHK_CHECKING)

    try:
        luhn_valid = is_valid_luhn(card_number)
        info       = await bin_lookup(card_number[:6])
        scheme     = (info.get("scheme") or "").lower()

        length_ok   = _check_length(card_number, scheme)
        expiry_ok, expiry_note = None, None
        if month and year:
            expiry_ok, expiry_note = _check_expiry(month, year)

        msg = chk_msg(
            card_number, luhn_valid, info,
            month=month, year=year, cvv=cvv,
            length_ok=length_ok,
            expiry_ok=expiry_ok, expiry_note=expiry_note,
        )
        await wait_msg.edit_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Chk error: {e}")
        await wait_msg.edit_text(MSG_ERROR)
