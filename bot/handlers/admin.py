import re
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import (
    get_detailed_stats, get_recent_users, get_banned_users,
    get_all_users, set_ban_status,
)
from bot.database.backup import USERS_JSON, get_all_local_users
from bot.database.bin_db import (
    get_top_bins, get_bin_db_size, get_total_requests_today,
    get_top_actions, get_user_summary, get_recent_bin_lookups,
)
from bot.utils.cache import bin_cache
from bot.config.settings import ADMIN_ID
from bot.utils.logger import get_logger

logger = get_logger("admin")

SEP = "─" * 20


def is_admin(user_id):
    return ADMIN_ID and user_id == ADMIN_ID


def _main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات",          callback_data="admin_stats")],
        [InlineKeyboardButton("👥 المشتركون",           callback_data="admin_all_users")],
        [InlineKeyboardButton("📈 نشاط المستخدمين",    callback_data="admin_user_activity")],
        [InlineKeyboardButton("💳 سجل BIN",            callback_data="admin_bin_log")],
        [InlineKeyboardButton("🚫 المحظورون",           callback_data="admin_ban_list")],
        [InlineKeyboardButton("📢 رسالة جماعية",       callback_data="admin_broadcast")],
        [InlineKeyboardButton("💾 نسخ احتياطي",        callback_data="admin_backup_file")],
    ])


def _back_btn():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]])


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
    today = get_total_requests_today()

    msg = (
        f"{SEP}\n"
        f"   🛠  DDXSTORE — لوحة التحكم\n"
        f"{SEP}\n\n"
        f"👥 المشتركون   │ {total}\n"
        f"✅ نشط          │ {active}\n"
        f"🚫 محظور        │ {banned}\n\n"
        f"🔄 توليد BIN    │ {gens}\n"
        f"💳 بحث BIN      │ {bin_lookups}\n"
        f"📊 طلبات اليوم │ {today}\n"
        f"📈 إجمالي       │ {requests}"
    )
    await update.message.reply_text(msg, reply_markup=_main_keyboard())


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /ban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id and set_ban_status(target_id, True):
        logger.info(f"Admin banned user {target_id}")
        await update.message.reply_text(f"🚫 تم حظر {target_id}")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /unban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id and set_ban_status(target_id, False):
        logger.info(f"Admin unbanned user {target_id}")
        await update.message.reply_text(f"✅ تم رفع الحظر عن {target_id}")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
    today_reqs = get_total_requests_today()
    top_bins   = get_top_bins(5)
    db_size    = get_bin_db_size()
    cache_size = bin_cache.size()
    top_actions = get_top_actions(5)

    bin_lines = ""
    if top_bins:
        bin_lines = "\n🏆 أكثر BIN طلباً:\n"
        for i, (b, c) in enumerate(top_bins, 1):
            bin_lines += f"   {i}. {b} — {c}x\n"

    action_lines = ""
    if top_actions:
        action_lines = "\n📋 الأوامر الأكثر استخداماً:\n"
        for action, cnt in top_actions:
            action_lines += f"   • {action}: {cnt}\n"

    msg = (
        f"{SEP}\n"
        f"   📊  DDXSTORE — إحصائيات\n"
        f"{SEP}\n\n"
        f"👥 المشتركون    │ {total}\n"
        f"✅ نشط           │ {active}\n"
        f"🚫 محظور         │ {banned}\n\n"
        f"🔄 توليد كروت   │ {gens}\n"
        f"💳 بحث BIN       │ {bin_lookups}\n"
        f"📈 إجمالي طلبات │ {requests}\n"
        f"📅 طلبات اليوم  │ {today_reqs}\n\n"
        f"🗄  قاعدة BIN    │ {db_size:,} إدخال\n"
        f"⚡  الكاش        │ {cache_size} إدخال"
        f"{bin_lines}"
        f"{action_lines}\n"
        f"{SEP}\n"
        f"   © DDXSTORE • @ddx22\n"
        f"{SEP}"
    )
    await update.message.reply_text(msg)


async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    full_text = update.message.text or ""
    bc_match = re.match(r"^/broadcast(@\w+)?\s*([\s\S]*)", full_text, re.IGNORECASE)
    msg = bc_match.group(2).strip() if bc_match else ""
    if not msg:
        await update.message.reply_text("❌ اكتب الرسالة بعد الأمر\n\nمثال: /broadcast مرحباً بالجميع")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("❌ لا يوجد مستخدمون.")
        return
    status_msg = await update.message.reply_text(f"⏳ جارٍ الإرسال لـ {len(users)} مستخدم...")
    success, failed = 0, 0
    for u_id in users:
        try:
            await context.bot.send_message(chat_id=u_id, text=msg)
            success += 1
            await asyncio.sleep(0.05)
        except Exception:
            failed += 1
    logger.info(f"Broadcast: {success} sent, {failed} failed")
    await status_msg.edit_text(f"✅ اكتمل الإرسال!\n\n✔ نجح: {success}\n✖ فشل: {failed}")


async def admin_callback(query, user):
    if not is_admin(user.id):
        return

    data = query.data

    if data == "admin_back":
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        today = get_total_requests_today()
        msg = (
            f"{SEP}\n"
            f"   🛠  DDXSTORE — لوحة التحكم\n"
            f"{SEP}\n\n"
            f"👥 المشتركون   │ {total}\n"
            f"✅ نشط          │ {active}\n"
            f"🚫 محظور        │ {banned}\n\n"
            f"🔄 توليد BIN    │ {gens}\n"
            f"💳 بحث BIN      │ {bin_lookups}\n"
            f"📊 طلبات اليوم │ {today}\n"
            f"📈 إجمالي       │ {requests}"
        )
        await query.edit_message_text(msg, reply_markup=_main_keyboard())

    elif data == "admin_stats":
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        today_reqs = get_total_requests_today()
        top_bins   = get_top_bins(5)
        db_size    = get_bin_db_size()
        cache_size = bin_cache.size()

        bin_lines = ""
        if top_bins:
            bin_lines = "\n🏆 أكثر BIN طلباً:\n"
            for i, (b, c) in enumerate(top_bins, 1):
                bin_lines += f"   {i}. {b} — {c}x\n"

        msg = (
            f"📊 الإحصائيات\n\n"
            f"👥 المشتركون    │ {total}\n"
            f"✅ نشط           │ {active}\n"
            f"🚫 محظور         │ {banned}\n\n"
            f"🔄 توليد كروت   │ {gens}\n"
            f"💳 بحث BIN       │ {bin_lookups}\n"
            f"📈 إجمالي طلبات │ {requests}\n"
            f"📅 طلبات اليوم  │ {today_reqs}\n\n"
            f"🗄  قاعدة BIN    │ {db_size:,} إدخال\n"
            f"⚡  الكاش        │ {cache_size} إدخال"
            f"{bin_lines}"
        )
        await query.edit_message_text(msg, reply_markup=_back_btn())

    elif data == "admin_all_users":
        users = get_all_local_users()
        if not users:
            await query.edit_message_text("لا يوجد مشتركون بعد.", reply_markup=_back_btn())
            return

        lines = [f"👥 المشتركون — {len(users)} مستخدم\n{SEP}"]
        for uid, uname, fname, joined in users[:20]:
            name = f"@{uname}" if uname else (fname or str(uid))
            date_str = joined[:10] if joined else "—"
            lines.append(f"• {name}  ({uid})\n  📅 {date_str}")

        if len(users) > 20:
            lines.append(f"\n... و {len(users) - 20} آخرين")

        await query.edit_message_text("\n".join(lines), reply_markup=_back_btn())

    elif data == "admin_user_activity":
        activity = get_user_summary(20)
        users_info = {uid: (uname, fname) for uid, uname, fname, _ in get_all_local_users()}

        if not activity:
            await query.edit_message_text("لا يوجد نشاط مسجّل بعد.", reply_markup=_back_btn())
            return

        lines = [f"📈 نشاط المستخدمين (Top 20)\n{SEP}"]
        for rank, (uid, total_reqs) in enumerate(activity, 1):
            uname, fname = users_info.get(uid, (None, None))
            name = f"@{uname}" if uname else (fname or str(uid))
            lines.append(f"{rank}. {name}  —  {total_reqs} طلب")

        await query.edit_message_text("\n".join(lines), reply_markup=_back_btn())

    elif data == "admin_bin_log":
        rows = get_recent_bin_lookups(15)

        if not rows:
            await query.edit_message_text("لا يوجد سجل BIN بعد.", reply_markup=_back_btn())
            return

        lines = [f"💳 آخر 15 بحث BIN\n{SEP}"]
        for uid, detail, ts, scheme, typ, bank, country, emoji in rows:
            bin_num   = (detail or "")[:6]
            scheme_s  = (scheme or "N/A").upper()
            typ_s     = (typ or "N/A").upper()
            bank_s    = (bank or "N/A").upper()
            country_s = (country or "N/A").upper()
            flag      = emoji or "🏳"
            time_s    = str(ts)[:16] if ts else "—"
            lines.append(
                f"• BIN: {bin_num}  │  {flag} {country_s}\n"
                f"  {scheme_s} - {typ_s} - {bank_s}\n"
                f"  👤 {uid}  │  🕐 {time_s}"
            )

        await query.edit_message_text("\n".join(lines), reply_markup=_back_btn())

    elif data == "admin_ban_list":
        banned_list = get_banned_users()
        if banned_list:
            lines = ["🚫 المستخدمون المحظورون:\n"]
            btns = []
            for uid, uname, fname in banned_list:
                name = f"@{uname}" if uname else fname or str(uid)
                lines.append(f"• {name}  ({uid})")
                btns.append([InlineKeyboardButton(f"رفع الحظر عن {name}", callback_data=f"unban_{uid}")])
            btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        else:
            await query.edit_message_text("لا يوجد مستخدمون محظورون.", reply_markup=_back_btn())

    elif data == "admin_backup_file":
        if USERS_JSON.exists():
            await query.message.reply_document(
                document=open(USERS_JSON, "rb"),
                filename="users_backup.json",
                caption="💾 نسخة احتياطية للمستخدمين",
            )
        else:
            await query.answer("❌ لا توجد بيانات")

    elif data.startswith("ban_") and not data.startswith("ban_list"):
        target_id = int(data.split("_")[1])
        if set_ban_status(target_id, True):
            logger.info(f"Admin banned {target_id} via panel")
            await query.answer(f"🚫 تم حظر {target_id}", show_alert=True)
        recent = get_recent_users(10)
        if recent:
            lines = ["👥 آخر 10 مستخدمين:\n"]
            btns = []
            for uid, uname, fname, joined in recent:
                name = f"@{uname}" if uname else fname or str(uid)
                date_str = joined.strftime("%m/%d %H:%M") if joined else "—"
                lines.append(f"• {name} ({uid}) - {date_str}")
                if uid != ADMIN_ID:
                    btns.append([InlineKeyboardButton(f"🚫 حظر {name}", callback_data=f"ban_{uid}")])
            btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))

    elif data.startswith("unban_"):
        target_id = int(data.split("_")[1])
        if set_ban_status(target_id, False):
            logger.info(f"Admin unbanned {target_id} via panel")
            await query.answer(f"✅ رُفع الحظر عن {target_id}", show_alert=True)
        banned_list = get_banned_users()
        if banned_list:
            lines = ["🚫 المستخدمون المحظورون:\n"]
            btns = []
            for uid, uname, fname in banned_list:
                name = f"@{uname}" if uname else fname or str(uid)
                lines.append(f"• {name}  ({uid})")
                btns.append([InlineKeyboardButton(f"رفع الحظر عن {name}", callback_data=f"unban_{uid}")])
            btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
            await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        else:
            await query.edit_message_text("لا يوجد مستخدمون محظورون.", reply_markup=_back_btn())

    elif data == "admin_broadcast":
        await query.edit_message_text(
            "أرسل: /broadcast <الرسالة>",
            reply_markup=_back_btn(),
        )
