import re
import html as _h
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import (
    get_detailed_stats, get_banned_users,
    get_all_users, set_ban_status, set_premium, get_premium_users_count,
    delete_user, get_users_page, search_user, get_user_info,
    set_setting, delete_setting,
)
from bot.utils.crypto import encrypt_value
from bot.database.backup import USERS_JSON
from bot.database.bin_db import (
    get_top_bins, get_bin_db_size, get_total_requests_today,
    get_top_actions, get_recent_bin_lookups,
)
from bot.utils.cache import bin_cache
from bot.config.settings import ADMIN_ID
from bot.utils.logger import get_logger

logger = get_logger("admin")

S  = "━" * 20
S2 = "─" * 20
PER_PAGE = 8

_bin_scheduler = None


def set_bin_scheduler(scheduler):
    global _bin_scheduler
    _bin_scheduler = scheduler


def is_admin(user_id):
    return ADMIN_ID and user_id == ADMIN_ID


# ─── Keyboards ────────────────────────────────────────────────────────────────

def _main_keyboard():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📊 الإحصائيات",       callback_data="admin_stats"),
            InlineKeyboardButton("👥 المستخدمون",        callback_data="admin_ul_0"),
        ],
        [
            InlineKeyboardButton("🚫 المحظورون",          callback_data="admin_ban_list"),
            InlineKeyboardButton("💎 Premium",            callback_data="admin_pl"),
        ],
        [
            InlineKeyboardButton("🗄 قاعدة BIN",          callback_data="admin_bin_db"),
            InlineKeyboardButton("📋 سجل BIN",            callback_data="admin_bin_log"),
        ],
        [InlineKeyboardButton("📢 بث رسالة: /broadcast <msg>", callback_data="admin_bc_info")],
        [InlineKeyboardButton("💾 نسخة احتياطية",          callback_data="admin_backup_file")],
    ])


def _back_btn(to="admin_back"):
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data=to)]])


def _user_actions_keyboard(uid: int, is_banned: bool, is_premium: bool, page: int = 0):
    ban_btn = (
        InlineKeyboardButton("✅ رفع الحظر",  callback_data=f"admin_ub_{uid}")
        if is_banned else
        InlineKeyboardButton("🚫 حظر",         callback_data=f"admin_ban_{uid}")
    )
    prem_btn = (
        InlineKeyboardButton("🔓 إلغاء Premium", callback_data=f"admin_rp_{uid}")
        if is_premium else
        InlineKeyboardButton("💎 منح Premium",   callback_data=f"admin_gp_{uid}")
    )
    return InlineKeyboardMarkup([
        [ban_btn, prem_btn],
        [InlineKeyboardButton("🗑 حذف المستخدم", callback_data=f"admin_del_{uid}")],
        [InlineKeyboardButton("🔙 قائمة المستخدمين", callback_data=f"admin_ul_{page}")],
        [InlineKeyboardButton("🏠 الرئيسية",          callback_data="admin_back")],
    ])


def _confirm_delete_keyboard(uid: int):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ تأكيد الحذف", callback_data=f"admin_dc_{uid}"),
            InlineKeyboardButton("❌ إلغاء",        callback_data=f"admin_uc_{uid}"),
        ],
    ])


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _build_main_msg(total, active, banned, gens, bin_lookups, requests, today, premium_c):
    return (
        f"{S}\n"
        f"   🛠  DDXSTORE — لوحة التحكم\n"
        f"{S}\n\n"
        f"👥 المستخدمون    ┃ <b>{total:,}</b>\n"
        f"✅ نشط            ┃ <b>{active:,}</b>\n"
        f"🚫 محظور          ┃ <b>{banned:,}</b>\n"
        f"💎 Premium        ┃ <b>{premium_c:,}</b>\n\n"
        f"🃏 توليد كروت    ┃ <b>{gens:,}</b>\n"
        f"🔍 بحث BIN       ┃ <b>{bin_lookups:,}</b>\n"
        f"📊 إجمالي طلبات  ┃ <b>{requests:,}</b>\n"
        f"📅 اليوم          ┃ <b>{today:,}</b>\n"
        f"{S}"
    )


def _build_user_card(info: dict) -> str:
    uname    = _h.escape(f"@{info['username']}") if info.get("username") else "—"
    fname    = _h.escape(info.get("first_name") or "—")
    uid      = info["user_id"]
    joined   = str(info.get("joined_at") or "—")[:10]
    reqs     = info.get("request_count", 0)
    gens     = info.get("gen_count", 0)
    chks     = info.get("chk_count", 0)
    prem     = "💎 Premium" if info.get("is_premium") else "🆓 Free"
    status   = "🚫 محظور" if info.get("is_banned") else "✅ نشط"
    prem_exp = ""
    if info.get("is_premium") and info.get("premium_until"):
        prem_exp = f"  <i>(حتى {str(info['premium_until'])[:10]})</i>"

    return (
        f"{S}\n"
        f"   👤  بطاقة المستخدم\n"
        f"{S}\n\n"
        f"🔗 المعرّف   ┃  {uname}\n"
        f"📛 الاسم     ┃  {fname}\n"
        f"🆔 ID        ┃  <code>{uid}</code>\n"
        f"📅 انضم      ┃  {joined}\n"
        f"{S2}\n"
        f"📊 الطلبات   ┃  <b>{reqs:,}</b>\n"
        f"🃏 الكروت    ┃  <b>{gens:,}</b>\n"
        f"🔍 الفحوصات  ┃  <b>{chks:,}</b>\n"
        f"🎖 عضوية    ┃  {prem}{prem_exp}\n"
        f"🔒 الحالة    ┃  {status}\n"
        f"{S}"
    )


# ─── Entry commands ───────────────────────────────────────────────────────────

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return

    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
    today    = get_total_requests_today()
    premium  = get_premium_users_count()
    msg = _build_main_msg(total, active, banned, gens, bin_lookups, requests, today, premium)
    await update.message.reply_text(msg, reply_markup=_main_keyboard(), parse_mode="HTML")


async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /ban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id == ADMIN_ID:
        await update.message.reply_text("❌ لا يمكنك حظر نفسك.")
        return
    if target_id and set_ban_status(target_id, True):
        logger.info(f"Admin banned user {target_id}")
        await update.message.reply_text(f"🚫 تم حظر <code>{target_id}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود أو حدث خطأ.")


async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not context.args:
        await update.message.reply_text("❌ الاستخدام: /unban <user_id>")
        return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if target_id and set_ban_status(target_id, False):
        logger.info(f"Admin unbanned user {target_id}")
        await update.message.reply_text(f"✅ رُفع الحظر عن <code>{target_id}</code>", parse_mode="HTML")
    else:
        await update.message.reply_text("❌ المستخدم غير موجود أو حدث خطأ.")


async def premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "❌ الاستخدام:\n"
            "/premium <user_id>        — اشتراك دائم\n"
            "/premium <user_id> 30     — اشتراك 30 يوم\n"
            "/unpremium <user_id>      — إلغاء الاشتراك"
        )
        return
    target_id = int(args[0]) if args[0].isdigit() else 0
    days = int(args[1]) if len(args) > 1 and args[1].isdigit() else None
    if not target_id:
        await update.message.reply_text("❌ ID غير صحيح")
        return
    ok = set_premium(target_id, True, days)
    if ok:
        note = f" لمدة {days} يوم" if days else " (دائم)"
        logger.info(f"Admin granted premium to {target_id}{note}")
        await update.message.reply_text(
            f"💎 تم منح Premium لـ <code>{target_id}</code>{note}", parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ لم يتم العثور على المستخدم.")


async def unpremium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    args = context.args or []
    if not args or not args[0].isdigit():
        await update.message.reply_text("❌ الاستخدام: /unpremium <user_id>")
        return
    target_id = int(args[0])
    ok = set_premium(target_id, False)
    if ok:
        logger.info(f"Admin revoked premium from {target_id}")
        await update.message.reply_text(
            f"🔓 تم إلغاء Premium عن <code>{target_id}</code>", parse_mode="HTML"
        )
    else:
        await update.message.reply_text("❌ لم يتم العثور على المستخدم.")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
    today_reqs = get_total_requests_today()
    top_bins   = get_top_bins(5)
    db_size    = get_bin_db_size()
    cache_size = bin_cache.size()
    top_actions = get_top_actions(5)
    premium    = get_premium_users_count()

    bin_lines = ""
    if top_bins:
        bin_lines = f"\n🏆 أكثر BIN طلباً:\n"
        for i, (b, c) in enumerate(top_bins, 1):
            bin_lines += f"   {i}. <code>{b}</code>  —  {c}x\n"

    action_lines = ""
    if top_actions:
        action_lines = f"\n📋 الأوامر الأكثر استخداماً:\n"
        for action, cnt in top_actions:
            action_lines += f"   • {action}: {cnt}\n"

    msg = (
        f"{S}\n"
        f"   📊  إحصائيات مفصّلة\n"
        f"{S}\n\n"
        f"👥 المستخدمون    ┃ <b>{total:,}</b>\n"
        f"✅ نشط            ┃ <b>{active:,}</b>\n"
        f"🚫 محظور          ┃ <b>{banned:,}</b>\n"
        f"💎 Premium        ┃ <b>{premium:,}</b>\n\n"
        f"🃏 توليد كروت    ┃ <b>{gens:,}</b>\n"
        f"🔍 بحث BIN       ┃ <b>{bin_lookups:,}</b>\n"
        f"📊 إجمالي طلبات  ┃ <b>{requests:,}</b>\n"
        f"📅 طلبات اليوم   ┃ <b>{today_reqs:,}</b>\n\n"
        f"🗄 قاعدة BIN      ┃ <b>{db_size:,}</b> إدخال\n"
        f"⚡ الكاش          ┃ <b>{cache_size}</b> إدخال"
        f"{bin_lines}"
        f"{action_lines}"
        f"\n{S}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")


async def user_info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    query_str = " ".join(context.args).strip() if context.args else ""
    if not query_str:
        await update.message.reply_text("❌ الاستخدام: /user <ID أو @username>")
        return
    info = search_user(query_str)
    if not info:
        await update.message.reply_text("❌ المستخدم غير موجود في قاعدة البيانات.")
        return
    uid = info["user_id"]
    card = _build_user_card(info)
    kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
    await update.message.reply_text(card, reply_markup=kb, parse_mode="HTML")


async def setkey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    args = context.args or []
    if not args:
        await update.message.reply_text(
            "❌ الاستخدام:\n<code>/setkey sk_live_...</code>\n<code>/setkey sk_test_...</code>",
            parse_mode="HTML",
        )
        return
    raw_key = args[0].strip()
    try:
        await update.message.delete()
    except Exception:
        pass
    if not (raw_key.startswith("sk_live_") or raw_key.startswith("sk_test_")):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ المفتاح يجب أن يبدأ بـ <code>sk_live_</code> أو <code>sk_test_</code>",
            parse_mode="HTML",
        )
        return
    encrypted = encrypt_value(raw_key)
    ok = set_setting("stripe_key", encrypted)
    if not ok:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="❌ فشل حفظ المفتاح — تحقق من قاعدة البيانات",
        )
        return
    masked = raw_key[:8] + "..." + raw_key[-4:]
    logger.info("Admin set Stripe key")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=f"✅ تم حفظ مفتاح Stripe\n<code>{_h.escape(masked)}</code>",
        parse_mode="HTML",
    )


async def removekey_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    ok = delete_setting("stripe_key")
    if ok:
        logger.info("Admin removed Stripe key")
        await update.message.reply_text("✅ تم حذف مفتاح Stripe")
    else:
        await update.message.reply_text("❌ لا يوجد مفتاح محفوظ")


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
            await asyncio.sleep(0.04 if success % 25 != 0 else 1.0)
        except Exception:
            failed += 1
    logger.info(f"Broadcast: {success} sent, {failed} failed")
    await status_msg.edit_text(f"✅ اكتمل الإرسال!\n\n✔ نجح: {success}\n✖ فشل: {failed}")


# ─── Callback handler ─────────────────────────────────────────────────────────

async def admin_callback(query, user):
    if not is_admin(user.id):
        return

    data = query.data

    # ══ EXACT matches first — then prefix matches ══════════════════════════════

    # ── رجوع للرئيسية ────────────────────────────────
    if data == "admin_back":
        await query.answer()
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        today   = get_total_requests_today()
        premium = get_premium_users_count()
        msg = _build_main_msg(total, active, banned, gens, bin_lookups, requests, today, premium)
        await query.edit_message_text(msg, reply_markup=_main_keyboard(), parse_mode="HTML")

    # ── إحصائيات مفصّلة ──────────────────────────────
    elif data == "admin_stats":
        await query.answer()
        total, active, banned, gens, bin_lookups, requests = get_detailed_stats()
        today    = get_total_requests_today()
        premium  = get_premium_users_count()
        top_bins = get_top_bins(5)
        db_size  = get_bin_db_size()
        cache_sz = bin_cache.size()

        bin_lines = ""
        if top_bins:
            bin_lines = "\n\n🏆 أكثر BIN طلباً:\n"
            for i, (b, c) in enumerate(top_bins, 1):
                bin_lines += f"   {i}. <code>{b}</code>  —  {c}x\n"

        msg = (
            f"{S}\n"
            f"   📊  إحصائيات مفصّلة\n"
            f"{S}\n\n"
            f"👥 المستخدمون    ┃ <b>{total:,}</b>\n"
            f"✅ نشط            ┃ <b>{active:,}</b>\n"
            f"🚫 محظور          ┃ <b>{banned:,}</b>\n"
            f"💎 Premium        ┃ <b>{premium:,}</b>\n\n"
            f"🃏 توليد كروت    ┃ <b>{gens:,}</b>\n"
            f"🔍 بحث BIN       ┃ <b>{bin_lookups:,}</b>\n"
            f"📊 إجمالي طلبات  ┃ <b>{requests:,}</b>\n"
            f"📅 اليوم          ┃ <b>{today:,}</b>\n\n"
            f"🗄 قاعدة BIN      ┃ <b>{db_size:,}</b> إدخال\n"
            f"⚡ الكاش          ┃ <b>{cache_sz}</b> إدخال"
            f"{bin_lines}"
            f"\n{S}"
        )
        await query.edit_message_text(msg, reply_markup=_back_btn(), parse_mode="HTML")

    # ── قائمة المحظورين (exact — must be before admin_ban_ prefix!) ───────────
    elif data == "admin_ban_list":
        await query.answer()
        banned_list = get_banned_users()
        if not banned_list:
            await query.edit_message_text("✅ لا يوجد مستخدمون محظورون.", reply_markup=_back_btn())
            return
        lines = [f"{S}\n   🚫  المحظورون — {len(banned_list)} مستخدم\n{S}\n"]
        btns  = []
        for uid, uname, fname in banned_list[:20]:
            name = _h.escape(f"@{uname}" if uname else (fname or str(uid)))
            lines.append(f"• {name}  <code>{uid}</code>")
            btns.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"admin_uc_{uid}")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
        await query.edit_message_text(
            "\n".join(lines), reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
        )

    # ── قائمة Premium (exact) ─────────────────────────
    elif data == "admin_pl":
        await query.answer()
        from bot.database.connection import execute_query
        rows = execute_query(
            """SELECT user_id, username, first_name, premium_until
               FROM bot_users WHERE is_premium = TRUE ORDER BY joined_at DESC""",
            fetch=True,
        ) or []
        if not rows:
            await query.edit_message_text("لا يوجد مشتركون Premium.", reply_markup=_back_btn())
            return
        lines = [f"{S}\n   💎  مشتركو Premium — {len(rows)} عضو\n{S}\n"]
        btns  = []
        for uid, uname, fname, until in rows[:20]:
            name = _h.escape(f"@{uname}" if uname else (fname or str(uid)))
            exp  = str(until)[:10] if until else "دائم"
            lines.append(f"• {name}  <code>{uid}</code>  📅 {exp}")
            btns.append([InlineKeyboardButton(f"👤 {name}", callback_data=f"admin_uc_{uid}")])
        btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
        await query.edit_message_text(
            "\n".join(lines), reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
        )

    # ── قاعدة BIN (exact) ────────────────────────────
    elif data == "admin_bin_db":
        await query.answer()
        await _show_bin_db(query)

    # ── سجل BIN (exact) ──────────────────────────────
    elif data == "admin_bin_log":
        await query.answer()
        rows = get_recent_bin_lookups(12)
        if not rows:
            await query.edit_message_text("لا يوجد سجل BIN بعد.", reply_markup=_back_btn())
            return
        lines = [f"{S}\n   💳  آخر 12 بحث BIN\n{S}\n"]
        for uid, detail, ts, scheme, typ, bank, country, emoji in rows:
            b   = (detail or "")[:6]
            sch = (scheme or "?").upper()
            ctr = (country or "?").upper()
            fl  = emoji or "🏳"
            tm  = str(ts)[:16] if ts else "—"
            lines.append(f"<code>{b}</code>  {fl} {ctr}  {sch}\n👤 {uid}  🕐 {tm}")
        await query.edit_message_text(
            "\n".join(lines), reply_markup=_back_btn(), parse_mode="HTML"
        )

    # ── بث (exact) ───────────────────────────────────
    elif data == "admin_bc_info":
        await query.answer()
        await query.edit_message_text(
            "📢 <b>بث رسالة</b>\n\nأرسل الأمر:\n<code>/broadcast الرسالة هنا</code>",
            reply_markup=_back_btn(),
            parse_mode="HTML",
        )

    # ── نسخة احتياطية (exact) ────────────────────────
    elif data == "admin_backup_file":
        if USERS_JSON.exists():
            with open(USERS_JSON, "rb") as f:
                await query.message.reply_document(
                    document=f,
                    filename="users_backup.json",
                    caption="💾 نسخة احتياطية للمستخدمين",
                )
            await query.answer("✅ تم الإرسال")
        else:
            await query.answer("❌ لا توجد بيانات", show_alert=True)

    # ── تحديث BIN (exact) ────────────────────────────
    elif data in ("admin_bin_update", "admin_bin_force"):
        force = (data == "admin_bin_force")
        if not _bin_scheduler:
            await query.answer("❌ المُحدِّث غير مفعّل", show_alert=True)
            return
        await query.answer("⏳ جاري التحديث..." if not force else "⚡ تحديث إجباري...")
        await query.edit_message_text("⏳ جاري تحديث قاعدة BIN...", reply_markup=_back_btn("admin_bin_db"))
        try:
            stats = await _bin_scheduler.run_now(force=force)
            msg = (
                f"✅ <b>اكتمل تحديث BIN</b>\n{S2}\n\n"
                f"🆕 جديد:      <b>{stats['new']}</b>\n"
                f"♻️ محدّث:     <b>{stats['updated']}</b>\n"
                f"❌ فشل:       <b>{stats['failed']}</b>\n"
                f"📦 إجمالي DB: <b>{stats['total_db']}</b>\n"
                f"⏱ الوقت:     <b>{stats['duration_s']}s</b>"
            )
            await query.edit_message_text(
                msg,
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_bin_db")]]),
                parse_mode="HTML",
            )
        except Exception as e:
            logger.error(f"admin_bin_update error: {e}")
            await query.edit_message_text(f"❌ خطأ: {e}", reply_markup=_back_btn("admin_bin_db"))

    # ══ PREFIX matches — all exact matches are handled above ═══════════════════

    # ── قائمة المستخدمين (paginated) ─────────────────
    elif data.startswith("admin_ul_"):
        await query.answer()
        page = int(data.split("_")[-1])
        rows, total = get_users_page(page, PER_PAGE)
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

        if not rows:
            await query.edit_message_text("لا يوجد مستخدمون بعد.", reply_markup=_back_btn())
            return

        header = (
            f"{S}\n"
            f"   👥  المستخدمون  —  صفحة {page + 1}/{total_pages}\n"
            f"{S}\n"
            f"إجمالي: <b>{total:,}</b> مستخدم\n"
        )

        btns = []
        for uid, uname, fname, is_banned, is_prem, reqs, gens, joined in rows:
            name  = _h.escape(f"@{uname}" if uname else (fname or str(uid)))
            badge = "🚫" if is_banned else ("💎" if is_prem else "")
            label = f"{badge} {name}  ({uid})" if badge else f"{name}  ({uid})"
            btns.append([InlineKeyboardButton(label, callback_data=f"admin_uc_{uid}")])

        nav = []
        if page > 0:
            nav.append(InlineKeyboardButton("◀️ السابق", callback_data=f"admin_ul_{page - 1}"))
        nav.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="admin_back"))
        if (page + 1) < total_pages:
            nav.append(InlineKeyboardButton("التالي ▶️", callback_data=f"admin_ul_{page + 1}"))
        btns.append(nav)
        btns.append([InlineKeyboardButton("🏠 الرئيسية", callback_data="admin_back")])

        await query.edit_message_text(
            header, reply_markup=InlineKeyboardMarkup(btns), parse_mode="HTML"
        )

    # ── بطاقة مستخدم ──────────────────────────────────
    elif data.startswith("admin_uc_"):
        await query.answer()
        uid  = int(data.split("_")[-1])
        info = get_user_info(uid)
        if not info:
            await query.answer("❌ المستخدم غير موجود", show_alert=True)
            return
        card = _build_user_card(info)
        kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
        await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")

    # ── حظر من البطاقة ────────────────────────────────
    elif data.startswith("admin_ban_"):
        uid = int(data.split("_")[-1])
        if uid == ADMIN_ID:
            await query.answer("❌ لا يمكنك حظر نفسك", show_alert=True)
            return
        if set_ban_status(uid, True):
            logger.info(f"Admin banned {uid} via panel")
            await query.answer("🚫 تم الحظر", show_alert=True)
        else:
            await query.answer()
        info = get_user_info(uid)
        if info:
            card = _build_user_card(info)
            kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")

    # ── رفع الحظر من البطاقة ──────────────────────────
    elif data.startswith("admin_ub_"):
        uid = int(data.split("_")[-1])
        if set_ban_status(uid, False):
            logger.info(f"Admin unbanned {uid} via panel")
            await query.answer("✅ تم رفع الحظر", show_alert=True)
        else:
            await query.answer()
        info = get_user_info(uid)
        if info:
            card = _build_user_card(info)
            kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")

    # ── منح Premium ───────────────────────────────────
    elif data.startswith("admin_gp_"):
        uid = int(data.split("_")[-1])
        if set_premium(uid, True):
            logger.info(f"Admin granted premium to {uid}")
            await query.answer("💎 تم منح Premium", show_alert=True)
        else:
            await query.answer()
        info = get_user_info(uid)
        if info:
            card = _build_user_card(info)
            kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")

    # ── إلغاء Premium ─────────────────────────────────
    elif data.startswith("admin_rp_"):
        uid = int(data.split("_")[-1])
        if set_premium(uid, False):
            logger.info(f"Admin revoked premium from {uid}")
            await query.answer("🔓 تم إلغاء Premium", show_alert=True)
        else:
            await query.answer()
        info = get_user_info(uid)
        if info:
            card = _build_user_card(info)
            kb   = _user_actions_keyboard(uid, info["is_banned"], info["is_premium"])
            await query.edit_message_text(card, reply_markup=kb, parse_mode="HTML")

    # ── طلب تأكيد الحذف ───────────────────────────────
    elif data.startswith("admin_del_"):
        await query.answer()
        uid  = int(data.split("_")[-1])
        info = get_user_info(uid)
        name = str(uid)
        if info:
            name = _h.escape(f"@{info['username']}" if info.get("username") else (info.get("first_name") or str(uid)))
        msg = (
            f"⚠️ <b>تأكيد الحذف</b>\n\n"
            f"هل تريد حذف المستخدم <b>{name}</b> (<code>{uid}</code>) نهائياً؟\n\n"
            f"<i>هذا الإجراء لا يمكن التراجع عنه.</i>"
        )
        await query.edit_message_text(msg, reply_markup=_confirm_delete_keyboard(uid), parse_mode="HTML")

    # ── تأكيد الحذف ───────────────────────────────────
    elif data.startswith("admin_dc_"):
        uid = int(data.split("_")[-1])
        ok  = delete_user(uid)
        if ok:
            logger.info(f"Admin deleted user {uid}")
            await query.answer("🗑 تم الحذف نهائياً", show_alert=True)
            msg = f"✅ تم حذف المستخدم <code>{uid}</code> من قاعدة البيانات."
            await query.edit_message_text(msg, reply_markup=_back_btn(), parse_mode="HTML")
        else:
            await query.answer("❌ فشل الحذف أو المستخدم غير موجود", show_alert=True)

    # ── Compat: old callbacks ─────────────────────────
    elif data.startswith("unban_"):
        uid = int(data.split("_")[1])
        if set_ban_status(uid, False):
            logger.info(f"Admin unbanned {uid} (compat)")
            await query.answer("✅ رُفع الحظر", show_alert=True)
        else:
            await query.answer()
        await query.edit_message_text("✅ تم رفع الحظر.", reply_markup=_back_btn())

    elif data.startswith("unpremium_"):
        uid = int(data.split("_")[1])
        if set_premium(uid, False):
            await query.answer("🔓 تم إلغاء Premium", show_alert=True)
        else:
            await query.answer()
        await query.edit_message_text("✅ تم إلغاء Premium.", reply_markup=_back_btn())

    else:
        await query.answer()


# ─── BIN DB view ─────────────────────────────────────────────────────────────

async def _show_bin_db(query):
    total = get_bin_db_size()
    top   = get_top_bins(5)

    status_txt = ""
    if _bin_scheduler:
        st  = _bin_scheduler.status()
        nxt = st.get("next_run_in")
        nxt_str = f"{nxt // 3600}h {(nxt % 3600) // 60}m" if nxt else "قريباً"
        ls  = st.get("last_stats") or {}
        status_txt = (
            f"\n⏱ التحديث القادم:  {nxt_str}\n"
            f"📦 آخر تحديث:  +{ls.get('new', '—')} جديد, {ls.get('updated', '—')} محدّث"
        )

    top_lines = "\n".join(
        f"   {i}. <code>{b}</code>  —  {c}x"
        for i, (b, c) in enumerate(top, 1)
    ) if top else "   لا توجد بيانات"

    msg = (
        f"{S}\n"
        f"   🗄  قاعدة بيانات BIN\n"
        f"{S}\n\n"
        f"📊 إجمالي BINs:  <b>{total:,}</b>"
        f"{status_txt}\n\n"
        f"🏆 <b>أكثر BIN طلباً:</b>\n{top_lines}\n"
        f"{S}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔄 تحديث الآن",    callback_data="admin_bin_update")],
        [InlineKeyboardButton("⚡ تحديث إجباري",  callback_data="admin_bin_force")],
        [InlineKeyboardButton("🔙 رجوع",          callback_data="admin_back")],
    ])
    await query.edit_message_text(msg, reply_markup=kb, parse_mode="HTML")


# ─── updatebins & randombin commands ─────────────────────────────────────────

async def updatebins_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not _bin_scheduler:
        await update.message.reply_text("❌ المُحدِّث غير مفعّل.")
        return
    force = bool(context.args and context.args[0].lower() == "force")
    wait  = await update.message.reply_text(
        f"⏳ جاري تحديث قاعدة BIN...{'  (إجباري)' if force else ''}"
    )
    try:
        stats = await _bin_scheduler.run_now(force=force)
        msg = (
            f"✅ <b>اكتمل تحديث BIN</b>\n{S2}\n\n"
            f"🆕 جديد:      <b>{stats['new']}</b>\n"
            f"♻️ محدّث:     <b>{stats['updated']}</b>\n"
            f"❌ فشل:       <b>{stats['failed']}</b>\n"
            f"📦 إجمالي DB: <b>{stats['total_db']}</b>\n"
            f"⏱ الوقت:     <b>{stats['duration_s']}s</b>"
        )
        await wait.edit_text(msg, parse_mode="HTML")
    except Exception as e:
        logger.error(f"updatebins command error: {e}")
        await wait.edit_text(f"❌ خطأ: {e}")


async def randombin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not is_admin(update.message.from_user.id):
        return
    if not _bin_scheduler:
        await update.message.reply_text("❌ المُحدِّث غير مفعّل.")
        return
    brand = context.args[0].upper() if len(context.args) > 0 else None
    type_ = context.args[1].upper() if len(context.args) > 1 else None
    cc    = context.args[2].upper() if len(context.args) > 2 else None
    row   = _bin_scheduler.updater.get_random_bin(brand=brand, type_=type_, country_code=cc)
    if not row:
        await update.message.reply_text(
            "❌ لم يُعثر على BIN بهذه الفلاتر.\n"
            "الاستخدام: /randombin [VISA/MC/AMEX] [CREDIT/DEBIT] [US/GB/SA]"
        )
        return
    msg = (
        f"🎲 <b>Random BIN</b>\n{S2}\n\n"
        f"🔢 BIN:     <code>{row.get('bin', '—')}</code>\n"
        f"🌐 Network: <b>{row.get('scheme', 'N/A')}</b>\n"
        f"📋 Type:    <b>{row.get('type', 'N/A')}</b>\n"
        f"⭐ Level:   <b>{row.get('level', 'N/A')}</b>\n"
        f"🏦 Bank:    {row.get('bank', 'N/A')}\n"
        f"🌍 Country: {row.get('country', 'N/A')} {row.get('emoji', '')}\n"
        f"💱 Currency:{row.get('currency', 'N/A')}\n"
        f"📡 Source:  {row.get('source', '—')}"
    )
    await update.message.reply_text(msg, parse_mode="HTML")
