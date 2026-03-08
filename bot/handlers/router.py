import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_stat, increment_request_count
from bot.database.bin_db import log_request
from bot.utils.validators import is_bin_pattern
from bot.utils.bin_lookup import bin_lookup
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.formatter import bin_lookup_msg, auto_gen_msg
from bot.services.country_service import find_country, get_country_info_text
from bot.services.i18n import DEFAULT_REPLY, MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD, BTN_GENERATE_AGAIN
from bot.config.settings import ADMIN_ID, DEFAULT_CARD_COUNT
from bot.utils.logger import get_logger

logger = get_logger("router")

_CARD_FULL_RE = re.compile(
    r"^(\d{6,19})[|/\-](\d{1,2})[|/\-](\d{2,4})([|/\-]\d{3,4})?$"
)
_GEN_PATTERN_RE = re.compile(r"^([\dxX]{6,19})$")
_PIPE_BIN_RE = re.compile(r"^(\d{6})")




async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_ID or not update.message:
        return
    user = update.message.from_user
    if not user or user.id == ADMIN_ID:
        return
    try:
        name = f"@{user.username}" if user.username else user.first_name or str(user.id)
        text = update.message.text or ""
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"\U0001f4e9 {name} ({user.id}):\n{text[:300]}",
        )
    except Exception:
        pass


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
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

    await forward_to_admin(update, context)

    text = update.message.text.strip()

    card_match = _CARD_FULL_RE.match(text)
    if card_match:
        digits = re.sub(r"[^0-9]", "", card_match.group(1))
        if len(digits) >= 6:
            logger.info(f"User {user.id} auto-detected card format: {text[:20]}")
            log_request(user.id, "auto_bin", digits[:6])
            increment_request_stat()
            increment_request_count(user.id)
            try:
                info = await bin_lookup(digits[:6])
                await update.message.reply_text(bin_lookup_msg(digits, info), parse_mode="HTML")
            except Exception:
                await update.message.reply_text(DEFAULT_REPLY)
            return

    raw = re.sub(r"[^0-9xX]", "", text)
    has_x = "x" in raw.lower()
    digit_part = re.sub(r"[^0-9]", "", raw.lower().split("x")[0] if has_x else raw)

    if has_x and len(digit_part) >= 6:
        logger.info(f"User {user.id} auto-detected generation pattern")
        log_request(user.id, "auto_gen", digit_part[:6])
        increment_request_stat()
        increment_request_count(user.id)
        from bot.utils.card_generator import generate_cards
        from bot.utils.bin_lookup import bin_lookup as _bl
        try:
            info = await _bl(digit_part[:6])
        except Exception:
            info = {"scheme": "N/A", "type": "N/A", "bank": "N/A",
                    "country": "N/A", "emoji": "\U0001f3f3\ufe0f"}
        cards = generate_cards(digit_part, DEFAULT_CARD_COUNT)
        msg = auto_gen_msg(user, digit_part, info, cards)
        callback_data = f"regen_{digit_part}_{DEFAULT_CARD_COUNT}"
        keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data=callback_data)]]
        await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        return

    if is_bin_pattern(text):
        digits = re.sub(r"[^0-9]", "", text)
        if len(digits) >= 6:
            logger.info(f"User {user.id} BIN lookup: {digits[:6]}")
            log_request(user.id, "bin", digits[:6])
            increment_request_stat()
            increment_request_count(user.id)
            try:
                from bot.database.queries import increment_bin_stat
                increment_bin_stat()
                info = await bin_lookup(digits[:6])
                await update.message.reply_text(bin_lookup_msg(digits, info), parse_mode="HTML")
            except Exception:
                pass
            return

    country_match, _ = await find_country(text)
    if country_match:
        log_request(user.id, "country", text[:50])
        increment_request_stat()
        increment_request_count(user.id)
        msg = get_country_info_text(country_match, False)
        await update.message.reply_text(msg, parse_mode="HTML")
        return

    await update.message.reply_text(DEFAULT_REPLY)
