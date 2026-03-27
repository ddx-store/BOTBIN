import html as _h
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, get_user_info, register_user, get_chk_count
from bot.config.settings import FREE_CHK_LIMIT, ADMIN_ID
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
        register_user(user.id, user.username, user.first_name)
        info = get_user_info(user.id)

    if not info:
        info = {
            "user_id":       user.id,
            "username":      user.username,
            "first_name":    user.first_name,
            "is_banned":     False,
            "is_premium":    False,
            "premium_until": None,
            "request_count": 0,
            "gen_count":     0,
            "chk_count":     0,
            "joined_at":     None,
        }

    username_str = _h.escape(f"@{info['username']}") if info.get("username") else "—"
    name_str     = _h.escape(info.get("first_name") or "—")

    joined = info.get("joined_at")
    joined_str = str(joined)[:10] if joined else "—"

    is_premium = info.get("is_premium", False)
    is_admin_user = ADMIN_ID and user.id == ADMIN_ID
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

    chk_used = info.get("chk_count", 0) or get_chk_count(user.id)
    if is_admin_user or is_premium:
        chk_line = f"♾ غير محدود"
    else:
        remaining = max(0, FREE_CHK_LIMIT - chk_used)
        chk_line = f"{chk_used}/{FREE_CHK_LIMIT} (متبقي: {remaining})"

    msg = (
        f"{SEP}\n"
        f"   👤  معلومات حسابي\n"
        f"{SEP}\n\n"
        f"🔗 المعرّف     :  {username_str}\n"
        f"📛 الاسم       :  {name_str}\n"
        f"🆔 ID          :  <code>{info['user_id']}</code>\n"
        f"📅 تاريخ الانضمام :  {joined_str}\n\n"
        f"📊 إجمالي الطلبات  :  {info['request_count']:,}\n"
        f"🃏 بطاقات مولّدة   :  {info['gen_count']:,}\n"
        f"🔍 فحوصات /chk     :  {chk_line}\n\n"
        f"🎖 الاشتراك    :  {member_line}\n"
        f"🔒 الحالة      :  {ban_str}\n\n"
        f"{SEP}\n"
        f"   <i>© DDXSTORE • @ddx22</i>\n"
        f"{SEP}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
