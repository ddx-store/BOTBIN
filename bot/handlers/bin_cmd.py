import re
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_bin_stat, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.bin_lookup import bin_lookup
from bot.utils.formatter import bin_lookup_msg
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
        msg = bin_lookup_msg(bin_input, info)
        await wait_msg.edit_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"BIN command error: {e}")
        await wait_msg.edit_text(MSG_BIN_ERROR)
