from telegram import Update, BotCommand
from telegram.ext import ContextTypes
from bot.database.queries import register_user
from bot.config.settings import ADMIN_ID
from bot.services.i18n import WELCOME_NEW, WELCOME_BACK, HELP_TEXT
from bot.utils.logger import get_logger

logger = get_logger("start")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    if not user:
        return
    is_new = register_user(user.id, user.username, user.first_name)

    if is_new:
        logger.info(f"New user: {user.id}")
        if ADMIN_ID:
            try:
                import html as _h
                from bot.database.backup import get_local_user_count
                total = get_local_user_count()
                name_d  = _h.escape(user.first_name or "—")
                uname_d = _h.escape(f"@{user.username}") if user.username else "—"
                notif = (
                    "🆕 مشترك جديد!\n"
                    "─────────────\n"
                    f"👤 الاسم  :  {name_d}\n"
                    f"🔗 المعرف :  {uname_d}\n"
                    f"🆔 ID     :  {user.id}\n"
                    "─────────────\n"
                    f"👥 إجمالي المشتركين: {total}"
                )
                await context.bot.send_message(chat_id=ADMIN_ID, text=notif)
            except Exception:
                pass
        import html as _h2
        safe_name = _h2.escape(user.first_name or "")
        await update.message.reply_text(WELCOME_NEW.format(name=safe_name))
    else:
        import html as _h2
        safe_name = _h2.escape(user.first_name or "")
        await update.message.reply_text(WELCOME_BACK.format(name=safe_name))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT)


async def setup_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start",   "ابدأ"),
        BotCommand("gen",     "توليد بطاقات"),
        BotCommand("bin",     "فحص BIN"),
        BotCommand("chk",     "فحص صحة بطاقة"),
        BotCommand("address", "عنوان عشوائي"),
        BotCommand("fake",    "هوية وهمية"),
        BotCommand("myinfo",  "معلوماتي"),
        BotCommand("help",    "دليل الاستخدام"),
    ])
