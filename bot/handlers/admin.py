import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import (
    get_detailed_stats, get_recent_users, get_banned_users,
    get_all_users, set_ban_status,
)
from bot.database.backup import USERS_JSON
from bot.database.bin_db import get_top_bins, get_bin_db_size, get_total_requests_today, get_top_actions
from bot.utils.cache import bin_cache
from bot.config.settings import ADMIN_ID
from bot.utils.logger import get_logger

logger = get_logger("admin")


def is_admin(user_id):
    return ADMIN_ID and user_id == ADMIN_ID


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()

    keyboard = [
        [InlineKeyboardButton("\U0001f4ca Stats", callback_data="admin_stats")],
        [InlineKeyboardButton("\U0001f465 Recent Users", callback_data="admin_recent")],
        [InlineKeyboardButton("\U0001f6ab Ban List", callback_data="admin_ban_list")],
        [InlineKeyboardButton("\U0001f4e2 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("\U0001f4be Backup", callback_data="admin_backup_file")],
    ]

    msg = (
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "   \U0001f6e0  DDXSTORE \u2014 Admin Panel\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f465 Total Users   \u2502 {total}\n"
        f"\u2705 Active        \u2502 {active}\n"
        f"\U0001f6ab Banned        \u2502 {banned}\n"
        f"\U0001f504 Generations   \u2502 {gens}\n"
        f"\U0001f4b3 BIN Lookups   \u2502 {bin_lookups}\n"
        f"\U0001f4ca Total Reqs    \u2502 {requests}"
    )

    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("\u274c Usage: /ban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id and set_ban_status(target_id, True):
        logger.info(f"Admin banned user {target_id}")
        await update.message.reply_text(f"\U0001f6ab Banned {target_id}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("\u274c Usage: /unban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id and set_ban_status(target_id, False):
        logger.info(f"Admin unbanned user {target_id}")
        await update.message.reply_text(f"\u2705 Unbanned {target_id}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
    today_reqs = get_total_requests_today()
    top_bins = get_top_bins(5)
    db_size = get_bin_db_size()
    cache_size = bin_cache.size()
    top_actions = get_top_actions(5)

    top_bin_lines = ""
    if top_bins:
        top_bin_lines = "\n\U0001f3c6 Top BINs:\n"
        for i, (b, c) in enumerate(top_bins, 1):
            top_bin_lines += f"   {i}. {b} \u2014 {c}x\n"

    top_action_lines = ""
    if top_actions:
        top_action_lines = "\n\U0001f4cb Top Actions:\n"
        for action, cnt in top_actions:
            top_action_lines += f"   \u2022 {action}: {cnt}\n"

    msg = (
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "   \U0001f4ca  DDXSTORE \u2014 Statistics\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f465 Total Users    \u2502 {total}\n"
        f"\u2705 Active         \u2502 {active}\n"
        f"\U0001f6ab Banned         \u2502 {banned}\n\n"
        f"\U0001f504 Card Gens      \u2502 {gens}\n"
        f"\U0001f4b3 BIN Lookups    \u2502 {bin_lookups}\n"
        f"\U0001f4ca Total Reqs     \u2502 {requests}\n"
        f"\U0001f4c5 Today Reqs     \u2502 {today_reqs}\n\n"
        f"\U0001f5c4  BIN DB Size   \u2502 {db_size} BINs\n"
        f"\u26a1  Cache Size    \u2502 {cache_size} entries"
        f"{top_bin_lines}"
        f"{top_action_lines}\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        "   \u00a9 DDXSTORE \u2022 @ddx22\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )
    await update.message.reply_text(msg)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    full_text = update.message.text or ""
    bc_match = re.match(r"^/broadcast(@\w+)?\s*([\s\S]*)", full_text, re.IGNORECASE)
    msg = bc_match.group(2).strip() if bc_match else ""
    if not msg:
        await update.message.reply_text("\u274c Write the message after the command\n\nExample: /broadcast Hello everyone")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("\u274c No users to send to.")
        return
    status_msg = await update.message.reply_text(f"\u23f3 Broadcasting to {len(users)} users...")
    success, failed = 0, 0
    for u_id in users:
        try:
            await context.bot.send_message(chat_id=u_id, text=msg)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    logger.info(f"Broadcast: {success} sent, {failed} failed")
    await status_msg.edit_text(f"\u2705 Broadcast complete!\n\nSuccess: {success}\nFailed: {failed}")


async def admin_callback(query, user):
    if not is_admin(user.id):
        return

    data = query.data

    if data == "admin_stats":
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        today_reqs = get_total_requests_today()
        top_bins = get_top_bins(5)
        db_size = get_bin_db_size()
        cache_size = bin_cache.size()

        top_bin_lines = ""
        if top_bins:
            top_bin_lines = "\n\U0001f3c6 Top BINs:\n"
            for i, (b, c) in enumerate(top_bins, 1):
                top_bin_lines += f"   {i}. {b} \u2014 {c}x\n"

        msg = (
            "\U0001f4ca Statistics\n\n"
            f"\U0001f465 Total Users    \u2502 {total}\n"
            f"\u2705 Active         \u2502 {active}\n"
            f"\U0001f6ab Banned         \u2502 {banned}\n\n"
            f"\U0001f504 Card Gens      \u2502 {gens}\n"
            f"\U0001f4b3 BIN Lookups    \u2502 {bin_lookups}\n"
            f"\U0001f4ca Total Reqs     \u2502 {requests}\n"
            f"\U0001f4c5 Today Reqs     \u2502 {today_reqs}\n\n"
            f"\U0001f5c4  BIN DB Size   \u2502 {db_size} BINs\n"
            f"\u26a1  Cache Size    \u2502 {cache_size} entries"
            f"{top_bin_lines}"
        )
        await query.edit_message_text(
            msg,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")]]
            ),
        )

    elif data == "admin_backup_file":
        if USERS_JSON.exists():
            await query.message.reply_document(
                document=open(USERS_JSON, "rb"),
                filename="users_backup.json",
                caption="\U0001f4be Users Backup",
            )
        else:
            await query.answer("\u274c No data available")

    elif data == "admin_recent":
        recent = get_recent_users(10)
        if recent:
            lines = ["\U0001f465 Recent 10 Users:\n"]
            btns = []
            for uid, uname, fname, joined in recent:
                name_display = f"@{uname}" if uname else fname or str(uid)
                date_str = joined.strftime("%m/%d %H:%M") if joined else "---"
                lines.append(f"\u2022 {name_display} ({uid}) - {date_str}")
                if uid != ADMIN_ID:
                    btns.append(
                        [InlineKeyboardButton(f"\U0001f6ab Ban {name_display}", callback_data=f"ban_{uid}")]
                    )
            btns.append([InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        else:
            await query.edit_message_text(
                "No users yet.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")]]
                ),
            )

    elif data == "admin_ban_list":
        banned_list = get_banned_users()
        if banned_list:
            lines = ["\U0001f6ab Banned Users:\n"]
            btns = []
            for uid, uname, fname in banned_list:
                name_display = f"@{uname}" if uname else fname or str(uid)
                lines.append(f"\u2022 {name_display} ({uid})")
                btns.append(
                    [InlineKeyboardButton(f"Unban {name_display}", callback_data=f"unban_{uid}")]
                )
            btns.append([InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        else:
            await query.edit_message_text(
                "No banned users.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")]]
                ),
            )

    elif data.startswith("ban_") and not data.startswith("ban_list"):
        target_id = int(data.split("_")[1])
        if set_ban_status(target_id, True):
            logger.info(f"Admin banned {target_id} via panel")
            await query.answer(f"\U0001f6ab Banned {target_id}", show_alert=True)
        recent = get_recent_users(10)
        if recent:
            lines = ["\U0001f465 Recent 10 Users:\n"]
            btns = []
            for uid, uname, fname, joined in recent:
                name_display = f"@{uname}" if uname else fname or str(uid)
                date_str = joined.strftime("%m/%d %H:%M") if joined else "---"
                lines.append(f"\u2022 {name_display} ({uid}) - {date_str}")
                if uid != ADMIN_ID:
                    btns.append(
                        [InlineKeyboardButton(f"\U0001f6ab Ban {name_display}", callback_data=f"ban_{uid}")]
                    )
            btns.append([InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("unban_"):
        target_id = int(data.split("_")[1])
        if set_ban_status(target_id, False):
            logger.info(f"Admin unbanned {target_id} via panel")
            await query.answer(f"\u2705 Unbanned {target_id}", show_alert=True)
        banned_list = get_banned_users()
        if banned_list:
            lines = ["\U0001f6ab Banned Users:\n"]
            btns = []
            for uid, uname, fname in banned_list:
                name_display = f"@{uname}" if uname else fname or str(uid)
                lines.append(f"\u2022 {name_display} ({uid})")
                btns.append(
                    [InlineKeyboardButton(f"Unban {name_display}", callback_data=f"unban_{uid}")]
                )
            btns.append([InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        else:
            await query.edit_message_text(
                "No banned users.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")]]
                ),
            )

    elif data == "admin_broadcast":
        await query.edit_message_text(
            "Send: /broadcast <message>",
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("\U0001f519 Back", callback_data="admin_back")]]
            ),
        )

    elif data == "admin_back":
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        keyboard = [
            [InlineKeyboardButton("\U0001f4ca Stats", callback_data="admin_stats")],
            [InlineKeyboardButton("\U0001f465 Recent Users", callback_data="admin_recent")],
            [InlineKeyboardButton("\U0001f6ab Ban List", callback_data="admin_ban_list")],
            [InlineKeyboardButton("\U0001f4e2 Broadcast", callback_data="admin_broadcast")],
            [InlineKeyboardButton("\U0001f4be Backup", callback_data="admin_backup_file")],
        ]
        msg = (
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
            "   \U0001f6e0  DDXSTORE \u2014 Admin Panel\n"
            "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
            f"\U0001f465 Total Users   \u2502 {total}\n"
            f"\u2705 Active        \u2502 {active}\n"
            f"\U0001f6ab Banned        \u2502 {banned}\n"
            f"\U0001f504 Generations   \u2502 {gens}\n"
            f"\U0001f4b3 BIN Lookups   \u2502 {bin_lookups}\n"
            f"\U0001f4ca Total Reqs    \u2502 {requests}"
        )
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
