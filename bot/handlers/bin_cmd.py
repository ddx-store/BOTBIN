import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_bin_stat, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.bin_lookup import bin_lookup
from bot.services.i18n import (
    MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD,
    MSG_BIN_EXAMPLE, MSG_BIN_LOOKUP, MSG_BIN_ERROR,
)
from bot.utils.logger import get_logger

logger = get_logger("bin_cmd")


async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    match = re.match(r"^/bin(@\w+)?\s*(.*)", text, re.IGNORECASE)
    bin_input = match.group(2).strip() if match else ""
    bin_input = re.sub(r"[^0-9]", "", bin_input)

    if not bin_input or len(bin_input) < 6:
        await update.message.reply_text(MSG_BIN_EXAMPLE)
        return

    increment_request_count(user.id)
    increment_bin_stat()
    increment_request_stat()
    log_request(user.id, "bin", bin_input[:6])
    logger.info(f"User {user.id} /bin {bin_input[:6]}")

    wait_msg = await update.message.reply_text(MSG_BIN_LOOKUP)
    try:
        info = await bin_lookup(bin_input[:8])
        prepaid_text = "Yes" if info.get("prepaid") else "No" if info.get("prepaid") is False else "N/A"
        msg = (
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \U0001f4b3  DDXSTORE \u2014 BIN Lookup\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\U0001f522  BIN      \u2502  {bin_input[:6]}\n"
            f"\U0001f3e6  Brand    \u2502  {info['scheme']}\n"
            f"\U0001f4c4  Type     \u2502  {info['type']}\n"
            f"\u2b50  Level    \u2502  {info['level']}\n"
            f"\U0001f3e0  Bank     \u2502  {info['bank']}\n"
            f"\U0001f30d  Country  \u2502  {info['country']}  {info['emoji']}\n"
            f"\U0001f4b0  Prepaid  \u2502  {prepaid_text}\n\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \u00a9 DDXSTORE \u2022 @ddx22\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )
        await wait_msg.edit_text(msg)
    except Exception as e:
        logger.error(f"BIN command error: {e}")
        await wait_msg.edit_text(MSG_BIN_ERROR)
