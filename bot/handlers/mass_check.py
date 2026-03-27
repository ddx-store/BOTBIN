import re
import asyncio
import httpx
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import (
    is_user_banned, increment_request_count, increment_request_stat,
    get_setting, is_premium_user, get_chk_count, increment_chk_count,
)
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.utils.luhn import is_valid_luhn
from bot.utils.formatter import mchk_line, mchk_msg
from bot.utils.crypto import decrypt_value
from bot.utils.stripe_checker import live_check
from bot.config.settings import FREE_CHK_LIMIT, ADMIN_ID
from bot.services.i18n import MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD
from bot.utils.logger import get_logger

logger = get_logger("mass_check")

MAX_MASS_CHECK = 50
MASS_CHECK_DELAY = 1.5
TG_MSG_LIMIT = 4000


def _parse_card_line(line: str):
    line = line.strip()
    if not line:
        return None
    parts = re.split(r"[|\s/\-]+", line)
    number = re.sub(r"[^0-9]", "", parts[0]) if parts else ""
    month = parts[1].zfill(2) if len(parts) > 1 and parts[1].isdigit() else None
    year = parts[2] if len(parts) > 2 and parts[2].isdigit() else None
    cvv = parts[3] if len(parts) > 3 and parts[3].isdigit() else None
    if year and len(year) == 4:
        year = year[2:]
    if not number or len(number) < 13 or len(number) > 19:
        return None
    if not month or not year or not cvv:
        return None
    return number, month, year, cvv


async def mchk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    is_admin = ADMIN_ID and user.id == ADMIN_ID
    is_prem = is_premium_user(user.id)

    text = update.message.text or ""
    match = re.match(r"^/mchk(@\w+)?\s*(.*)", text, re.IGNORECASE | re.DOTALL)
    raw_input = match.group(2).strip() if match else ""

    if not raw_input:
        await update.message.reply_text(
            "❌ أرسل البطاقات بعد الأمر\n\n"
            "<b>مثال:</b>\n"
            "<code>/mchk\n"
            "4510141234567890|08|29|123\n"
            "5200831234567890|05|27|456</code>\n\n"
            f"📊 الحد الأقصى: {MAX_MASS_CHECK} بطاقة",
            parse_mode="HTML",
        )
        return

    lines = raw_input.split("\n")
    cards = []
    for line in lines:
        parsed = _parse_card_line(line)
        if parsed:
            cards.append(parsed)

    if not cards:
        await update.message.reply_text(
            "❌ لم يتم العثور على بطاقات صالحة\n\n"
            "الصيغة: <code>رقم|شهر|سنة|CVV</code>",
            parse_mode="HTML",
        )
        return

    if len(cards) > MAX_MASS_CHECK:
        cards = cards[:MAX_MASS_CHECK]

    if not is_admin and not is_prem:
        used = get_chk_count(user.id)
        remaining = max(0, FREE_CHK_LIMIT - used)
        if remaining <= 0:
            await update.message.reply_text(
                f"❌ استنفذت الفحوصات المجانية ({FREE_CHK_LIMIT}/{FREE_CHK_LIMIT})\n\n"
                "💎 للحصول على فحوصات غير محدودة، تحتاج اشتراك <b>Premium</b>\n"
                "تواصل مع الأدمن @ddx22 للترقية",
                parse_mode="HTML",
            )
            return
        if len(cards) > remaining:
            cards = cards[:remaining]

    enc_key = get_setting("stripe_key")
    if not enc_key:
        await update.message.reply_text("❌ مفتاح الفحص غير مُعَد. تواصل مع الأدمن.")
        return

    try:
        stripe_key = decrypt_value(enc_key)
    except Exception:
        await update.message.reply_text("❌ خطأ في مفتاح الفحص.")
        return

    total = len(cards)
    wait_msg = await update.message.reply_text(
        f"⏳ جاري فحص {total} بطاقة...\n📊 0/{total}",
    )

    results = []
    live_count = 0
    dead_count = 0
    err_count = 0

    async with httpx.AsyncClient(timeout=15) as http_client:
        for i, (number, month, year, cvv) in enumerate(cards):
            try:
                luhn_ok = is_valid_luhn(number)
                if not luhn_ok:
                    lr = {"status": "dead", "display": "Invalid Luhn", "decline_code": "luhn_fail", "raw_message": "", "gate": ""}
                else:
                    lr = await live_check(number, month, year, cvv, stripe_key, client=http_client)

                st = lr.get("status", "unknown")
                if st == "live":
                    live_count += 1
                elif st in ("dead", "ccv_error"):
                    dead_count += 1
                else:
                    err_count += 1

                results.append(mchk_line(number, month, year, cvv, lr))

            except Exception as e:
                logger.error(f"Mass check error card {i}: {e}")
                err_count += 1
                results.append(f"⚠️  <code>{number[:6]}••••{number[-4:]}</code>")

            if not is_admin and not is_prem:
                increment_chk_count(user.id)

            increment_request_count(user.id)
            increment_request_stat()
            log_request(user.id, "mchk", number[:6])

            if (i + 1) % 5 == 0 or i == total - 1:
                try:
                    await wait_msg.edit_text(
                        f"⏳ جاري الفحص... {i+1}/{total}\n"
                        f"✅ {live_count}  ❌ {dead_count}  ⚠️ {err_count}",
                    )
                except Exception:
                    pass

            if i < total - 1:
                await asyncio.sleep(MASS_CHECK_DELAY)

    msg = mchk_msg(results, total, live_count, dead_count, err_count, user)

    if len(msg) > TG_MSG_LIMIT:
        mid = len(results) // 2
        msg1 = mchk_msg(results[:mid], total, live_count, dead_count, err_count, user)
        msg2 = mchk_msg(results[mid:], total, live_count, dead_count, err_count, user)
        try:
            await wait_msg.edit_text(msg1, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(msg1, parse_mode="HTML")
        await update.message.reply_text(msg2, parse_mode="HTML")
    else:
        try:
            await wait_msg.edit_text(msg, parse_mode="HTML")
        except Exception:
            await update.message.reply_text(msg, parse_mode="HTML")
