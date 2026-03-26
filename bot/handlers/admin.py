import re
import asyncio
import time
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

_bin_scheduler = None

def set_bin_scheduler(scheduler):
    global _bin_scheduler
    _bin_scheduler = scheduler


def is_admin(user_id):
    return ADMIN_ID and user_id == ADMIN_ID


def _main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 إحصائيات",          callback_data="admin_stats")],
        [InlineKeyboardButton("👥 المشتركون",           callback_data="admin_all_users")],
        [InlineKeyboardButton("📈 نشاط المستخدمين",    callback_data="admin_user_activity")],
        [InlineKeyboardButton("💳 سجل BIN",            callback_data="admin_bin_log")],
        [InlineKeyboardButton("🗄 قاعدة BIN",          callback_data="admin_bin_db")],
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


async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    query_str = " ".join(context.args).strip() if context.args else ""
    if not query_str:
        await update.message.reply_text("❌ الاستخدام: /user <ID أو @username>")
        return

    import json
    from pathlib import Path
    from bot.database.bin_db import get_user_summary, get_recent_bin_lookups

    users_json = Path("data/users.json")
    all_users = {}
    if users_json.exists():
        try:
            all_users = json.loads(users_json.read_text(encoding="utf-8"))
        except Exception:
            pass

    found_uid, found_info = None, None
    q = query_str.lstrip("@").lower()
    for uid, info in all_users.items():
        uname = (info.get("username") or "").lower()
        if uid == q or uname == q:
            found_uid = int(uid)
            found_info = info
            break

    if not found_uid and q.isdigit():
        found_uid = int(q)
        found_info = all_users.get(q, {})

    if not found_uid:
        await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
        return

    name_d  = found_info.get("first_name") or "—"
    uname_d = f"@{found_info.get('username')}" if found_info.get("username") else "—"
    joined  = (found_info.get("joined_at") or "—")[:10]

    user_activity = {uid: total for uid, total in get_user_summary(200)}
    total_reqs = user_activity.get(found_uid, 0)

    recent_bins = [(detail[:6], scheme or "?", country or "?")
                   for uid, detail, ts, scheme, typ, bank, country, emoji
                   in get_recent_bin_lookups(50) if uid == found_uid][:5]

    bin_lines = ""
    if recent_bins:
        bin_lines = "\n💳 آخر BINs:\n"
        for b, s, c in recent_bins:
            bin_lines += f"  • {b}  ({s} — {c})\n"

    msg = (
        f"👤 معلومات المستخدم\n{SEP}\n"
        f"🔗 المعرف  :  {uname_d}\n"
        f"📛 الاسم   :  {name_d}\n"
        f"🆔 ID      :  {found_uid}\n"
        f"📅 انضم    :  {joined}\n"
        f"{SEP}\n"
        f"📊 إجمالي الطلبات  :  {total_reqs}"
        f"{bin_lines}"
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

    elif data == "admin_bin_db":
        await _show_bin_db(query)

    elif data in ("admin_bin_update", "admin_bin_force"):
        force = (data == "admin_bin_force")
        if not _bin_scheduler:
            await query.answer("❌ المُحدِّث غير مفعّل", show_alert=True)
            return
        await query.answer("⏳ جاري التحديث..." if not force else "⚡ تحديث إجباري...")
        await query.edit_message_text(
            "⏳ جاري تحديث قاعدة BIN، انتظر قليلاً...",
            reply_markup=_back_btn(),
        )
        try:
            stats = await _bin_scheduler.run_now(force=force)
            msg = (
                f"✅ <b>اكتمل تحديث BIN</b>\n"
                f"{'─' * 20}\n\n"
                f"🆕 جديد:       <b>{stats['new']}</b>\n"
                f"♻️ محدّث:      <b>{stats['updated']}</b>\n"
                f"❌ فشل:        <b>{stats['failed']}</b>\n"
                f"📦 إجمالي DB:  <b>{stats['total_db']}</b>\n"
                f"⏱ الوقت:      <b>{stats['duration_s']}s</b>"
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 رجوع", callback_data="admin_bin_db")],
            ])
            await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            logger.error(f"admin_bin_update error: {e}")
            await query.edit_message_text(f"❌ خطأ: {e}", reply_markup=_back_btn())


async def _show_bin_db(query):
    total = get_bin_db_size()
    top   = get_top_bins(5)

    status_txt = ""
    if _bin_scheduler:
        st = _bin_scheduler.status()
        nxt = st.get("next_run_in")
        nxt_str = f"{nxt // 3600}h {(nxt % 3600) // 60}m" if nxt else "قريباً"
        ls  = st.get("last_stats") or {}
        status_txt = (
            f"\n⏱ التحديث القادم: {nxt_str}\n"
            f"📦 آخر تحديث: +{ls.get('new', '—')} جديد, {ls.get('updated', '—')} محدّث"
        )

    top_lines = "\n".join(f"   {i}. <code>{b}</code>  —  {c}x"
                          for i, (b, c) in enumerate(top, 1)) if top else "   لا توجد بيانات"

    msg = (
        f"🗄  <b>قاعدة بيانات BIN</b>\n"
        f"{'─' * 22}\n\n"
        f"📊 إجمالي BINs في DB: <b>{total}</b>"
        f"{status_txt}\n\n"
        f"🏆 <b>أكثر BIN طلباً:</b>\n{top_lines}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث الآن",      callback_data="admin_bin_update")],
        [InlineKeyboardButton("⚡ تحديث إجباري",    callback_data="admin_bin_force")],
        [InlineKeyboardButton("🔙 رجوع",            callback_data="admin_back")],
    ])
    await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")


async def updatebins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /updatebins [force] — trigger BIN database update."""
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not _bin_scheduler:
        await update.message.reply_text("❌ المُحدِّث غير مفعّل.")
        return

    force = bool(context.args and context.args[0].lower() == "force")
    wait  = await update.message.reply_text(
        "⏳ جاري تحديث قاعدة BIN...\n"
        f"{'(تحديث إجباري)' if force else ''}"
    )
    try:
        stats = await _bin_scheduler.run_now(force=force)
        msg = (
            f"✅ <b>اكتمل تحديث BIN</b>\n"
            f"{'─' * 20}\n\n"
            f"🆕 جديد:       <b>{stats['new']}</b>\n"
            f"♻️ محدّث:      <b>{stats['updated']}</b>\n"
            f"❌ فشل:        <b>{stats['failed']}</b>\n"
            f"📦 إجمالي DB:  <b>{stats['total_db']}</b>\n"
            f"⏱ الوقت:      <b>{stats['duration_s']}s</b>"
        )
        await wait.edit_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"updatebins command error: {e}")
        await wait.edit_text(f"❌ خطأ: {e}")


async def randombin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command: /randombin [brand] [type] [country] — get a random BIN."""
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not _bin_scheduler:
        await update.message.reply_text("❌ المُحدِّث غير مفعّل.")
        return

    brand = context.args[0].upper() if len(context.args) > 0 else None
    type_ = context.args[1].upper() if len(context.args) > 1 else None
    cc    = context.args[2].upper() if len(context.args) > 2 else None

    row = _bin_scheduler.updater.get_random_bin(brand=brand, type_=type_, country_code=cc)
    if not row:
        await update.message.reply_text(
            "❌ لم يُعثر على BIN بهذه الفلاتر.\n"
            "استخدام: /randombin [VISA/MC/AMEX] [CREDIT/DEBIT] [US/GB/SA]"
        )
        return

    bin_num   = row.get("bin", "—")
    scheme    = row.get("scheme", "N/A")
    typ       = row.get("type", "N/A")
    level     = row.get("level", "N/A")
    bank      = row.get("bank", "N/A")
    country   = row.get("country", "N/A")
    ccode     = row.get("country_code", "")
    emoji     = row.get("emoji") or ""
    currency  = row.get("currency", "N/A")
    source    = row.get("source", "—")

    msg = (
        f"🎲 <b>Random BIN</b>\n"
        f"{'─' * 20}\n\n"
        f"🔢 BIN:       <code>{bin_num}</code>\n"
        f"🌐 Network:   <b>{scheme}</b>\n"
        f"📋 Type:      <b>{typ}</b>\n"
        f"⭐ Level:     <b>{level}</b>\n"
        f"🏦 Bank:      {bank}\n"
        f"🌍 Country:   {country} {emoji}\n"
        f"💱 Currency:  {currency}\n"
        f"📡 Source:    {source}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
