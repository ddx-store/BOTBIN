import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.services.country_service import find_country, get_address_text
from bot.services.i18n import MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD, MSG_ADDR_EXAMPLE, MSG_ADDR_NOT_FOUND, BTN_GENERATE_AGAIN


async def address_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    match = re.match(r"^/address(@\w+)?\s*(.*)", text, re.IGNORECASE)
    country_input = match.group(2).strip() if match else ""

    if not country_input:
        await update.message.reply_text(MSG_ADDR_EXAMPLE)
        return

    increment_request_count(user.id)
    increment_request_stat()
    log_request(user.id, "address", country_input[:50])

    country_match, use_arabic = await find_country(country_input)
    if not country_match:
        await update.message.reply_text(MSG_ADDR_NOT_FOUND.format(country=country_input))
        return

    country_name = country_match["name"]
    msg = get_address_text(country_name, False)
    keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data=f"addr_{country_name}")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def address_regen_callback(query, user):
    data = query.data
    country_name = data.replace("addr_", "", 1)
    msg = get_address_text(country_name, False)
    keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data=f"addr_{country_name}")]]
    try:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass
