import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.luhn import is_valid_luhn
from bot.utils.bin_lookup import bin_lookup
from bot.services.i18n import (
    MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD,
    MSG_CHK_EXAMPLE, MSG_CHK_CHECKING, MSG_ERROR,
)
from bot.utils.logger import get_logger

logger = get_logger("check")


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

    text = update.message.text
    match = re.match(r"^/(?:chk|check)(@\w+)?\s*(.*)", text, re.IGNORECASE)
    card_input = match.group(2).strip() if match else ""
    parts = re.split(r"[|\s\-]+", card_input)
    card_number = re.sub(r"[^0-9]", "", parts[0]) if parts else ""

    if not card_number or len(card_number) < 13 or len(card_number) > 19:
        await update.message.reply_text(MSG_CHK_EXAMPLE)
        return

    increment_request_count(user.id)
    increment_request_stat()
    log_request(user.id, "chk", card_number[:6])
    logger.info(f"User {user.id} /chk BIN={card_number[:6]}")

    wait_msg = await update.message.reply_text(MSG_CHK_CHECKING)

    try:
        valid = is_valid_luhn(card_number)
        info = await bin_lookup(card_number[:6])

        if valid:
            status_icon = "\u2705"
            status_text = "VALID"
            luhn_text = "Luhn Valid \u2714"
        else:
            status_icon = "\u274c"
            status_text = "INVALID"
            luhn_text = "Luhn Invalid \u2718"

        masked = card_number[:6] + "\u2022" * (len(card_number) - 10) + card_number[-4:]

        msg = (
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            f"   {status_icon}  DDXSTORE \u2014 Card Check\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\U0001f4b3  Card     \u2502  {masked}\n"
            f"\U0001f50d  Status   \u2502  {status_text}\n"
            f"\U0001f9ee  Luhn     \u2502  {luhn_text}\n"
            f"\U0001f3e6  Brand    \u2502  {info['scheme']}\n"
            f"\U0001f4c4  Type     \u2502  {info['type']}\n"
            f"\U0001f3e0  Bank     \u2502  {info['bank']}\n"
            f"\U0001f30d  Country  \u2502  {info['country']}  {info['emoji']}\n\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \u00a9 DDXSTORE \u2022 @ddx22\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )
        await wait_msg.edit_text(msg)
    except Exception as e:
        logger.error(f"Chk error: {e}")
        await wait_msg.edit_text(MSG_ERROR)
