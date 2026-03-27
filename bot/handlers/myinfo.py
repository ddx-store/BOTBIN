import html as _h
from telegram import Update
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, get_user_info, register_user, get_chk_count
from bot.config.settings import FREE_CHK_LIMIT, ADMIN_ID
from bot.utils.logger import get_logger

logger = get_logger("myinfo")

S = "━" * 16


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

    uname = _h.escape(f"@{info['username']}") if info.get("username") else "—"
    name = _h.escape(info.get("first_name") or "—")
    uid = info["user_id"]

    joined = info.get("joined_at")
    joined_str = str(joined)[:10] if joined else "—"

    is_premium = info.get("is_premium", False)
    is_admin_user = ADMIN_ID and user.id == ADMIN_ID

    if is_admin_user:
        tier = "👑 Admin"
    elif is_premium:
        pu = info.get("premium_until")
        tier = f"💎 Premium — {str(pu)[:10]}" if pu else "💎 Premium"
    else:
        tier = "🆓 Free"

    chk_used = info.get("chk_count", 0) or get_chk_count(user.id)
    if is_admin_user or is_premium:
        chk_line = "♾"
    else:
        remaining = max(0, FREE_CHK_LIMIT - chk_used)
        chk_line = f"{remaining}/{FREE_CHK_LIMIT}"

    reqs = info.get("request_count", 0)
    gens = info.get("gen_count", 0)

    msg = (
        f"{S}\n"
        f"  👤  <b>{name}</b>  {uname}\n"
        f"{S}\n"
        f"🆔  <code>{uid}</code>\n"
        f"📅  {joined_str}\n"
        f"{S}\n"
        f"📊  Requests: <b>{reqs:,}</b>\n"
        f"🃏  Generated: <b>{gens:,}</b>\n"
        f"🔍  Checks: <b>{chk_line}</b>\n"
        f"{S}\n"
        f"🎖  {tier}\n"
        f"{S}\n"
        f"<i>© DDXSTORE • @ddx22</i>"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
