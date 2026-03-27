import html as _h
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, get_user_info
from bot.utils.logger import get_logger

logger = get_logger("myinfo")

SEP = "─" * 18


async def myinfo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    if not user:
        return

    if is_user_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور.")
        return

    info = get_user_info(user.id)

    if not info:
        await update.message.reply_text(
            "❌ لم يتم العثور على بياناتك.\n"
            "أرسل /start لتسجيل حسابك أولاً."
        )
        return

    username_str = _h.escape(f"@{info['username']}") if info.get("username") else "—"
    name_str     = _h.escape(info.get("first_name") or "—")

    joined = info.get("joined_at")
    joined_str = str(joined)[:10] if joined else "—"

    is_premium = info.get("is_premium", False)
    premium_until = info.get("premium_until")

    if is_premium:
        if premium_until:
            exp_str = str(premium_until)[:10]
            member_line = f"💎 Premium (حتى {exp_str})"
        else:
            member_line = "💎 Premium (دائم)"
    else:
        member_line = "🆓 Free"

    ban_str = "🚫 محظور" if info.get("is_banned") else "✅ نشط"

    msg = (
        f"{SEP}\n"
        f"   👤  معلومات حسابي\n"
        f"{SEP}\n\n"
        f"🔗 المعرّف     :  {username_str}\n"
        f"📛 الاسم       :  {name_str}\n"
        f"🆔 ID          :  <code>{info['user_id']}</code>\n"
        f"📅 تاريخ الانضمام :  {joined_str}\n\n"
        f"📊 إجمالي الطلبات  :  {info['request_count']:,}\n"
        f"🃏 بطاقات مولّدة   :  {info['gen_count']:,}\n\n"
        f"🎖 الاشتراك    :  {member_line}\n"
        f"🔒 الحالة      :  {ban_str}\n\n"
        f"{SEP}\n"
        f"   <i>© DDXSTORE • @ddx22</i>\n"
        f"{SEP}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
