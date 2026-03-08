import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import (
    is_user_banned, increment_gen_stat, increment_request_count, increment_request_stat,
)
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.card_generator import generate_cards
from bot.utils.luhn import is_valid_luhn
from bot.utils.bin_lookup import bin_lookup
from bot.utils.queue_manager import enqueue_task, LARGE_GEN_THRESHOLD
from bot.utils.formatter import gen_msg
from bot.services.i18n import (
    MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD, MSG_PROCESSING, MSG_ERROR,
    MSG_INVALID_BIN, MSG_GEN_EXAMPLE, MSG_QUEUED, MSG_QUEUE_FULL, BTN_GENERATE_AGAIN,
)
from bot.config.settings import DEFAULT_CARD_COUNT, MAX_CARD_COUNT
from bot.utils.logger import get_logger

logger = get_logger("gen")


async def format_gen_response(user, bin_input, count=DEFAULT_CARD_COUNT, fixed_month=None, fixed_year=None):
    increment_gen_stat()
    increment_request_stat()
    log_request(user.id, "gen", bin_input[:8])

    prefix = re.sub(r"[^0-9]", "", bin_input.lower().split("x")[0] if "x" in bin_input.lower() else bin_input)

    try:
        info = await bin_lookup(prefix[:6])
    except Exception:
        info = {"scheme": "N/A", "type": "N/A", "bank": "N/A", "country": "N/A", "emoji": "\U0001f3f3\ufe0f"}

    raw_cards = generate_cards(prefix, count, fixed_month, fixed_year)
    cards = [c for c in raw_cards if is_valid_luhn(c["number"])]
    msg = gen_msg(user, prefix, info, cards,
                  bin_input=bin_input, fixed_month=fixed_month, fixed_year=fixed_year,
                  checked=len(cards))

    callback_data = f"regen_{prefix}_{count}"
    if fixed_month and fixed_year:
        callback_data += f"_{fixed_month}_{fixed_year}"

    keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data=callback_data)]]
    return msg, InlineKeyboardMarkup(keyboard)


def _parse_gen_input(text: str):
    match = re.match(r"^/gen(@\w+)?\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    full_input = match.group(2).strip() if match else text.strip()
    if not full_input:
        return None, None, None, None

    pipe_match = re.match(
        r"^([\dxX]{6,19})[|/\-](\d{1,2})[|/\-](\d{2,4})(?:[|/\-](\d+))?$",
        full_input.strip(),
        re.IGNORECASE,
    )
    if pipe_match:
        bin_input = pipe_match.group(1)
        month = pipe_match.group(2).zfill(2)
        year = pipe_match.group(3)
        count_str = pipe_match.group(4)
        count = min(int(count_str), MAX_CARD_COUNT) if count_str and count_str.isdigit() else DEFAULT_CARD_COUNT
        if len(year) == 4:
            year = year[2:]
        return bin_input, month, year, count

    clean_input = re.sub(r"[|\-/]", " ", full_input)
    parts = clean_input.split()
    bin_input, month, year = None, None, None
    count = DEFAULT_CARD_COUNT

    for part in parts:
        if re.match(r"^[\dXx]{6,}$", part):
            bin_input = part
            break

    if not bin_input:
        return None, None, None, None

    remaining = [p for p in parts if p != bin_input and p.isdigit()]

    if len(remaining) >= 2:
        p1, p2 = remaining[0], remaining[1]
        try:
            if 1 <= int(p1) <= 12:
                month, year = p1.zfill(2), p2
            elif 1 <= int(p2) <= 12:
                month, year = p2.zfill(2), p1
        except ValueError:
            pass
        if year and len(year) == 4:
            year = year[2:]
        if len(remaining) >= 3 and remaining[2].isdigit():
            count = min(int(remaining[2]), MAX_CARD_COUNT)
    elif len(remaining) == 1:
        val = int(remaining[0])
        if 2 <= val <= MAX_CARD_COUNT:
            count = val

    return bin_input, month, year, count


async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    if not user:
        return

    from bot.handlers.router import forward_to_admin
    await forward_to_admin(update, context)

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
    bin_input, month, year, count = _parse_gen_input(text)

    if not bin_input:
        await update.message.reply_text(MSG_GEN_EXAMPLE)
        return

    raw_digits = re.sub(r"[^0-9]", "", bin_input.lower().split("x")[0] if "x" in bin_input.lower() else bin_input)
    if len(raw_digits) < 6:
        await update.message.reply_text(MSG_INVALID_BIN)
        return

    increment_request_count(user.id)
    logger.info(f"User {user.id} /gen BIN={raw_digits[:6]} count={count}")

    if count > LARGE_GEN_THRESHOLD:
        wait_msg = await update.message.reply_text(MSG_QUEUED)

        async def _task():
            try:
                msg, markup = await format_gen_response(user, bin_input, count, month, year)
                await wait_msg.delete()
                await update.message.reply_text(msg, reply_markup=markup, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Queue gen error: {e}")
                await wait_msg.edit_text(MSG_ERROR)

        queued = await enqueue_task(user.id, _task())
        if not queued:
            await wait_msg.edit_text(MSG_QUEUE_FULL)
    else:
        wait_msg = await update.message.reply_text(MSG_PROCESSING)
        try:
            msg, markup = await format_gen_response(user, bin_input, count, month, year)
            await wait_msg.delete()
            await update.message.reply_text(msg, reply_markup=markup, parse_mode="HTML")
        except Exception as e:
            logger.error(f"Gen error: {e}")
            await wait_msg.edit_text(MSG_ERROR)


async def regen_callback(query, user):
    data = query.data
    parts = data.split("_")
    bin_val = parts[1]
    count = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else DEFAULT_CARD_COUNT
    month = parts[3] if len(parts) > 4 else None
    year = parts[4] if len(parts) > 4 else None

    count = min(count, MAX_CARD_COUNT)

    try:
        msg, markup = await format_gen_response(user, bin_val, count, month, year)
        await query.edit_message_text(msg, reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Regen callback error: {e}")
