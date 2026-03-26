import os
import traceback
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from bot.config.settings import BOT_TOKEN
from bot.database.models import init_db
from bot.handlers.start import start, help_command, setup_commands
from bot.handlers.gen import gen_command, regen_callback
from bot.handlers.bin_cmd import bin_command
from bot.handlers.check import chk_command
from bot.handlers.address import address_command, address_regen_callback
from bot.handlers.fake import fake_command, fake_regen_callback
from bot.handlers.myinfo import myinfo_command
from bot.handlers.admin import (
    admin_panel, ban_command, unban_command,
    broadcast_command, stats_command, admin_callback,
    user_info_command, updatebins_command, randombin_command,
    premium_command, unpremium_command,
    set_bin_scheduler,
)
from bot.handlers.router import text_router
from bot.database.queries import is_user_banned
from bot.services.bin_updater import BinUpdateScheduler
from bot.utils.logger import get_logger

logger = get_logger("app")

WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

_scheduler: BinUpdateScheduler | None = None


async def button_callback(update, context):
    query = update.callback_query
    user  = query.from_user
    if is_user_banned(user.id):
        await query.answer("\U0001f6ab")
        return

    data = query.data
    if data.startswith("regen_"):
        await query.answer("\u23f3")
        await regen_callback(query, user)
    elif data.startswith("addr_"):
        await query.answer("\U0001f504")
        await address_regen_callback(query, user)
    elif data.startswith("fake_"):
        await query.answer("\U0001f504")
        await fake_regen_callback(query, user)
    elif (data.startswith("admin_") or data.startswith("ban_")
          or data.startswith("unban_") or data.startswith("unpremium_")):
        await admin_callback(query, user)


async def post_init(application):
    global _scheduler
    init_db()
    await setup_commands(application)

    _scheduler = BinUpdateScheduler(
        interval_s       = 24 * 3600,
        initial_delay_s  = 90,
    )
    _scheduler.start(application)
    set_bin_scheduler(_scheduler)

    logger.info("Bot initialized successfully.")
    print("DDXSTORE Bot is running.")


def create_app():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set.")
        return None

    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CommandHandler("bin", bin_command))
    app.add_handler(CommandHandler("chk", chk_command))
    app.add_handler(CommandHandler("check", chk_command))
    app.add_handler(CommandHandler("address", address_command))
    app.add_handler(CommandHandler("fake", fake_command))
    app.add_handler(CommandHandler("myinfo",     myinfo_command))
    app.add_handler(CommandHandler("admin",      admin_panel))
    app.add_handler(CommandHandler("ban",        ban_command))
    app.add_handler(CommandHandler("unban",      unban_command))
    app.add_handler(CommandHandler("broadcast",  broadcast_command))
    app.add_handler(CommandHandler("stats",      stats_command))
    app.add_handler(CommandHandler("user",       user_info_command))
    app.add_handler(CommandHandler("updatebins", updatebins_command))
    app.add_handler(CommandHandler("randombin",  randombin_command))
    app.add_handler(CommandHandler("premium",    premium_command))
    app.add_handler(CommandHandler("unpremium",  unpremium_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Regex(r"^/gen\d+"), gen_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"Exception while handling update: {context.error}")
        logger.error(traceback.format_exception(type(context.error), context.error, context.error.__traceback__))
        if isinstance(update, Update) and update.effective_message:
            try:
                await update.effective_message.reply_text("⚠️ حدث خطأ أثناء معالجة طلبك. حاول مرة أخرى.")
            except Exception:
                pass

    app.add_error_handler(error_handler)

    return app


def run():
    app = create_app()
    if not app:
        return

    dev_domain     = os.getenv("REPLIT_DEV_DOMAIN")
    railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL")
    custom_webhook = os.getenv("WEBHOOK_URL")

    webhook_domain = custom_webhook or (
        f"https://{dev_domain}" if dev_domain else (
            f"https://{railway_domain}" if railway_domain else None
        )
    )

    if webhook_domain:
        webhook_url = webhook_domain.rstrip("/") + "/webhook"
        logger.info(f"Starting webhook mode → {webhook_url} (port {WEBHOOK_PORT})")
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path="/webhook",
            webhook_url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("Starting polling mode (no webhook domain detected)...")
        app.run_polling(drop_pending_updates=True)
