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
        logger.info(f"New user: {user.id} @{user.username}")
        if ADMIN_ID:
            try:
                from bot.database.backup import get_local_user_count
                total = get_local_user_count()
                name_d  = user.first_name or "—"
                uname_d = f"@{user.username}" if user.username else "—"
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
        await update.message.reply_text(WELCOME_NEW.format(name=user.first_name))
    else:
        await update.message.reply_text(WELCOME_BACK.format(name=user.first_name))


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT)


async def setup_commands(application):
    await application.bot.set_my_commands([
        BotCommand("start", "\u0627\u0628\u062f\u0623"),
        BotCommand("gen", "\u062a\u0648\u0644\u064a\u062f \u0628\u0637\u0627\u0642\u0627\u062a"),
        BotCommand("bin", "\u0641\u062d\u0635 BIN"),
        BotCommand("chk", "\u0641\u062d\u0635 \u0635\u062d\u0629 \u0628\u0637\u0627\u0642\u0629"),
        BotCommand("address", "\u0639\u0646\u0648\u0627\u0646 \u0639\u0634\u0648\u0627\u0626\u064a"),
        BotCommand("fake", "\u0647\u0648\u064a\u0629 \u0648\u0647\u0645\u064a\u0629"),
        BotCommand("help", "\u062f\u0644\u064a\u0644 \u0627\u0644\u0627\u0633\u062a\u062e\u062f\u0627\u0645"),
    ])
