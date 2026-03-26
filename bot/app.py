import os
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from bot.config.settings import BOT_TOKEN
from bot.database.models import init_db
from bot.handlers.start import start, help_command, setup_commands
from bot.handlers.gen import gen_command, regen_callback
from bot.handlers.bin_cmd import bin_command
from bot.handlers.check import chk_command
from bot.handlers.address import address_command, address_regen_callback
from bot.handlers.fake import fake_command, fake_regen_callback
from bot.handlers.admin import (
    admin_panel, ban_command, unban_command,
    broadcast_command, stats_command, admin_callback,
    user_info_command,
)
from bot.handlers.router import text_router
from bot.database.queries import is_user_banned
from bot.utils.logger import get_logger

logger = get_logger("app")

WEBHOOK_PORT = 8080


async def button_callback(update, context):
    query = update.callback_query
    user = query.from_user
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
    elif data.startswith("admin_") or data.startswith("ban_") or data.startswith("unban_"):
        await admin_callback(query, user)


async def post_init(application):
    init_db()
    await setup_commands(application)
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
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("user", user_info_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Regex(r"^/gen\d+"), gen_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    return app


def run():
    app = create_app()
    if not app:
        return

    dev_domain = os.getenv("REPLIT_DEV_DOMAIN")

    if dev_domain:
        webhook_url = f"https://{dev_domain}/webhook"
        logger.info(f"Starting webhook mode → {webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path="/webhook",
            webhook_url=webhook_url,
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query"],
        )
    else:
        logger.info("Starting polling mode...")
        app.run_polling(drop_pending_updates=True)
