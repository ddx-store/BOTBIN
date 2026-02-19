import os
import re
import random
import httpx
import psycopg2
import asyncio
import time
import json
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters, CallbackQueryHandler

# تنبيه: يجب أن يكون ملف country_autodetect.py في نفس المجلد
try:
    import country_autodetect
except ImportError:
    country_autodetect = None

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
COPYRIGHT = "© DDXSTORE"
ADMIN_ID_STR = os.getenv("ADMIN_ID", "0")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else 0

# [NEW] Backup System for Non-DB environments
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
USERS_JSON = DATA_DIR / "users.json"
BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(exist_ok=True)

# --- Backup Helpers ---
def _local_register_user(user_id, username, first_name):
    """حفظ نسخة محلية احتياطية للمشتركين لضمان عدم ضياعهم"""
    try:
        users = {}
        if USERS_JSON.exists():
            try:
                users = json.loads(USERS_JSON.read_text(encoding="utf-8"))
            except: pass
        
        str_id = str(user_id)
        if str_id not in users:
            users[str_id] = {
                "username": username,
                "first_name": first_name,
                "joined_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            USERS_JSON.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
            
            # نسخة احتياطية يومية
            timestamp = datetime.now().strftime("%Y%m%d")
            daily_backup = BACKUP_DIR / f"users_backup_{timestamp}.json"
            if not daily_backup.exists():
                daily_backup.write_text(json.dumps(users, ensure_ascii=False), encoding="utf-8")
    except: pass

# --- Database Functions ---

def init_db():
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                is_banned BOOLEAN DEFAULT FALSE,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS bot_stats (
                key TEXT PRIMARY KEY,
                value BIGINT DEFAULT 0
            )
        """)
        cur.execute("INSERT INTO bot_stats (key, value) VALUES ('total_gens', 0) ON CONFLICT DO NOTHING")
        cur.execute("""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='bot_users' AND column_name='is_banned') THEN
                    ALTER TABLE bot_users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE;
                END IF;
            END $$;
        """)
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e: print(f"DB Init Error: {e}")

def register_user(user_id, username, first_name):
    # دائماً احفظ نسخة احتياطية محلية لضمان عدم فقدان المشتركين
    _local_register_user(user_id, username, first_name)
    
    if not DATABASE_URL: return False
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM bot_users WHERE user_id = %s", (user_id,))
        exists = cur.fetchone()
        is_new = False
        if not exists:
            cur.execute("INSERT INTO bot_users (user_id, username, first_name) VALUES (%s, %s, %s)", (user_id, username, first_name))
            is_new = True
        conn.commit()
        cur.close()
        conn.close()
        return is_new
    except Exception: return False

def is_user_banned(user_id):
    if not DATABASE_URL: return False
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT is_banned FROM bot_users WHERE user_id = %s", (user_id,))
        result = cur.fetchone()
        cur.close()
        conn.close()
        return result[0] if result else False
    except Exception: return False

def set_ban_status(user_id, status):
    if not DATABASE_URL: return False
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("UPDATE bot_users SET is_banned = %s WHERE user_id = %s", (status, user_id))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception: return False

def increment_gen_stat():
    if not DATABASE_URL: return
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("UPDATE bot_stats SET value = value + 1 WHERE key = 'total_gens'")
        conn.commit()
        cur.close()
        conn.close()
    except Exception: pass

def get_stats():
    if not DATABASE_URL:
        # جلب العدد من الملف المحلي في حال عدم وجود قاعدة بيانات
        try:
            if USERS_JSON.exists():
                data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
                return len(data), 0
        except: pass
        return 0, 0
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bot_users")
        u_count = cur.fetchone()[0]
        cur.execute("SELECT value FROM bot_stats WHERE key = 'total_gens'")
        g_count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return u_count, g_count
    except Exception: return 0, 0

def get_all_users():
    if not DATABASE_URL:
        try:
            if USERS_JSON.exists():
                data = json.loads(USERS_JSON.read_text(encoding="utf-8"))
                return [int(uid) for uid in data.keys()]
        except: pass
        return []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT user_id FROM bot_users WHERE is_banned = FALSE")
        users = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return users
    except Exception: return []

def get_banned_users():
    if not DATABASE_URL: return []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, first_name FROM bot_users WHERE is_banned = TRUE")
        users = cur.fetchall()
        cur.close()
        conn.close()
        return users
    except Exception: return []

def get_detailed_stats():
    # محاولة جلب العدد المحلي أولاً لضمان الدقة
    local_count = 0
    try:
        if USERS_JSON.exists():
            local_count = len(json.loads(USERS_JSON.read_text(encoding="utf-8")))
    except: pass

    if not DATABASE_URL: return local_count, local_count, 0, 0
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM bot_users")
        total = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bot_users WHERE is_banned = FALSE")
        active = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bot_users WHERE is_banned = TRUE")
        banned = cur.fetchone()[0]
        cur.execute("SELECT value FROM bot_stats WHERE key = 'total_gens'")
        gens = cur.fetchone()[0]
        cur.close()
        conn.close()
        return max(total, local_count), active, banned, gens
    except Exception: return local_count, local_count, 0, 0

def get_recent_users(limit=10):
    if not DATABASE_URL: return []
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT user_id, username, first_name, joined_at FROM bot_users ORDER BY joined_at DESC LIMIT %s", (limit,))
        users = cur.fetchall()
        cur.close()
        conn.close()
        return users
    except Exception: return []

USER_RATE_LIMIT = {}
RATE_LIMIT_MAX = 15
RATE_LIMIT_WINDOW = 60

def check_rate_limit(user_id):
    now = time.time()
    if user_id not in USER_RATE_LIMIT:
        USER_RATE_LIMIT[user_id] = []
    USER_RATE_LIMIT[user_id] = [t for t in USER_RATE_LIMIT[user_id] if now - t < RATE_LIMIT_WINDOW]
    if len(USER_RATE_LIMIT[user_id]) >= RATE_LIMIT_MAX:
        return False
    USER_RATE_LIMIT[user_id].append(now)
    return True

# --- Generation Logic ---

def luhn_checksum(card_number):
    def digits_of(n): return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits: checksum += sum(digits_of(d * 2))
    return checksum % 10

def calculate_luhn(partial_card_number):
    return (10 - luhn_checksum(partial_card_number * 10)) % 10

def generate_card_from_prefix(prefix, total_length=16):
    prefix = re.sub(r'[^0-9]', '', str(prefix))
    if not prefix: return None
    prefix_length = len(prefix)
    if prefix_length >= total_length:
        prefix = prefix[:total_length - 1]
        prefix_length = total_length - 1
    remaining = total_length - prefix_length - 1
    if remaining < 0: return None
    middle_digits = ''.join(str(random.randint(0, 9)) for _ in range(remaining))
    partial = prefix + middle_digits
    check = calculate_luhn(int(partial))
    return partial + str(check)

def generate_expiry():
    now = datetime.now()
    future_year = now.year + random.randint(1, 5)
    month = random.randint(1, 12)
    return f"{month:02d}", f"{str(future_year)}"

def generate_cvv():
    return f"{random.randint(0, 999):03d}"

async def bin_lookup(bin_number):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f'https://lookup.binlist.net/{bin_number}',
                headers={'Accept-Version': '3'},
                timeout=4 # تقليل وقت الانتظار لتجنب التعليق
            )
        if response.status_code == 200:
            data = response.json()
            scheme = data.get('scheme', 'N/A').upper()
            card_type = data.get('type', 'N/A').upper()
            bank = data.get('bank', {}).get('name', 'N/A')
            country = data.get('country', {}).get('name', 'N/A')
            emoji = data.get('country', {}).get('emoji', '🏳️')
            return scheme, card_type, bank, country, emoji
        return "N/A", "N/A", "N/A", "N/A", "🏳️"
    except Exception:
        return "N/A", "N/A", "N/A", "N/A", "🏳️"

# --- Bot Handlers ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user = update.message.from_user
    if not user: return
    is_new = register_user(user.id, user.username, user.first_name)
    if is_new:
        if ADMIN_ID:
            try: await context.bot.send_message(chat_id=ADMIN_ID, text=f"🆕 مستخدم جديد: {user.first_name} (@{user.username})")
            except Exception: pass
        await update.message.reply_text(
            f"مرحبا {user.first_name}! 👋\n\n"
            f"أهلا فيك في بوت DDXSTORE\n\n"
            f"الأوامر المتاحة:\n"
            f"/gen <BIN> - توليد بطاقات\n"
            f"/help - المساعدة\n\n"
            f"جرب الآن: /gen 451014\n\n"
            f"© DDXSTORE"
        )
    else:
        await update.message.reply_text(
            f"أهلا من جديد {user.first_name}! 👋\n\n"
            f"/gen <BIN> - ادخل معلومات البطاقة كالتالي\n"
            f"/help - المساعدة\n\n"
            f"© DDXSTORE"
        )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID: return
    
    # إضافة عرض عدد المشتركين مباشرة في لوحة التحكم
    total, active, banned, gens = get_detailed_stats()
    
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 آخر المستخدمين", callback_data="admin_recent")],
        [InlineKeyboardButton("🚫 قائمة المحظورين", callback_data="admin_ban_list")],
        [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
        [InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup_file")],
    ]
    
    msg = (
        f"🛠 لوحة تحكم المدير:\n\n"
        f"👥 إجمالي المشتركين: {total}\n"
        f"🔄 إجمالي التوليدات: {gens}"
    )
    
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def process_gen(user, bin_input, fixed_month=None, fixed_year=None):
    increment_gen_stat()
    prefix = re.sub(r'[^0-9]', '', bin_input.lower().split('x')[0] if 'x' in bin_input.lower() else bin_input)
    
    # محاولة جلب المعلومات مع معالجة التعليق
    try:
        scheme, card_type, bank, country, emoji = await bin_lookup(prefix[:6])
    except:
        scheme, card_type, bank, country, emoji = "N/A", "N/A", "N/A", "N/A", "🏳️"
    
    lines = []
    for _ in range(10):
        card = generate_card_from_prefix(prefix)
        m, y = (fixed_month, fixed_year) if fixed_month and fixed_year else generate_expiry()
        cvv = generate_cvv()
        lines.append(f"<code>{card}|{m}|{y}|{cvv}</code>")
    
    # إضافة معلومات العنوان إذا توفرت
    extra_addr = ""
    if country_autodetect and country != "N/A":
        try:
            addr = country_autodetect.get_random_address(country)
            if addr:
                extra_addr = f"\n📍 Addr ⌁ {addr['city']}, {addr['zip']}"
        except: pass

    msg = (
        f"み​ ¡Rimuru_CHk↯  ⌁  CC Generator\n\n"
        f"• Bin ⌁ ({prefix[:6]})\n"
        f"• Info ⌁ {scheme} - {card_type} - CLASSIC\n"
        f"• Bank ⌁ {bank}\n"
        f"• Country ⌁ {country.upper()}  {emoji}\n"
        f"• Format ⌁ {prefix[:12]}|x|x|x\n\n"
        + "\n".join(lines) + "\n\n"
        f"• ReqBy ⌁ @{user.username if user.username else user.first_name}\n"
        f"• DevBy ⌁ @ddx22"
    )
    
    callback_data = f"regen_{prefix}"
    if fixed_month and fixed_year:
        callback_data += f"_{fixed_month}_{fixed_year}"
        
    keyboard = [[InlineKeyboardButton("🔄 Generate Again", callback_data=callback_data)]]
    return msg, InlineKeyboardMarkup(keyboard)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    await update.message.reply_text(
        "📖 دليل استخدام البوت\n\n"
        "🔹 /gen <BIN> - توليد 10 بطاقات\n"
        "   مثال: /gen 451014\n"
        "   مع تاريخ: /gen 451014 08 2029\n\n"
        "🔹 /start - بدء البوت\n"
        "🔹 /help - عرض هذه الرسالة\n\n"
        "🌍 أرسل اسم أي دولة وبيطلع لك معلوماتها\n\n"
        "© DDXSTORE"
    )

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user = update.message.from_user
    if not user: return
    if is_user_banned(user.id):
        await update.message.reply_text("🚫 أنت محظور.")
        return
    if not check_rate_limit(user.id):
        await update.message.reply_text("⏳ انتظر قليلا قبل ما تستخدم الأمر مرة ثانية.")
        return
    
    text = update.message.text
    match = re.match(r'^/gen(@\w+)?\s*(.*)', text, re.IGNORECASE | re.DOTALL)
    full_input = match.group(2).strip() if match else text.strip()
    if not full_input:
        await update.message.reply_text('❌ مثال: /gen 505xxxxxxxxxxxxxx 03 2030')
        return

    clean_input = re.sub(r'[|\-/]', ' ', full_input)
    parts = clean_input.split()
    bin_input, month, year = None, None, None
    for part in parts:
        if re.match(r'^[\dXx]{6,}$', part): bin_input = part; break
    if not bin_input:
        await update.message.reply_text('❌ لم أجد BIN صحيح.')
        return

    remaining = [p for p in parts if p != bin_input and p.isdigit()]
    if len(remaining) >= 2:
        p1, p2 = remaining[0], remaining[1]
        if 1 <= int(p1) <= 12: month, year = p1.zfill(2), p2
        elif 1 <= int(p2) <= 12: month, year = p2.zfill(2), p1
        if year and len(year) == 4: year = year[2:]

    await forward_to_admin(update, context)
    
    # إضافة رسالة انتظار لتجنب شعور المستخدم بالتعليق
    wait_msg = await update.message.reply_text("⏳ Processing...")
    
    try:
        msg, markup = await process_gen(user, bin_input, month, year)
        await wait_msg.delete()
        await update.message.reply_text(msg, reply_markup=markup, parse_mode='HTML')
    except:
        await wait_msg.edit_text("❌ Error processing your request.")

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if set_ban_status(target_id, True): await update.message.reply_text(f"🚫 تم حظر {target_id}")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID: return
    if not context.args: return
    target_id = int(context.args[0]) if context.args[0].isdigit() else 0
    if set_ban_status(target_id, False): await update.message.reply_text(f"✅ تم فك حظر {target_id}")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID: return
    full_text = update.message.text or ""
    bc_match = re.match(r'^/broadcast(@\w+)?\s*([\s\S]*)', full_text, re.IGNORECASE)
    msg = bc_match.group(2).strip() if bc_match else ""
    if not msg:
        await update.message.reply_text("❌ اكتب الرسالة بعد الأمر\n\nمثال: /broadcast مرحبا بالجميع")
        return
    users = get_all_users()
    if not users:
        await update.message.reply_text("❌ لا يوجد مستخدمين لإرسال الرسالة لهم.")
        return
    status_msg = await update.message.reply_text(f"⏳ جاري النشر لـ {len(users)} مستخدم...")
    success, failed = 0, 0
    for u_id in users:
        try:
            await context.bot.send_message(chat_id=u_id, text=msg)
            success += 1
            await asyncio.sleep(0.05)
        except Exception: failed += 1
    await status_msg.edit_text(f"✅ تم النشر!\n\nناجح: {success}\nفاشل: {failed}")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    if is_user_banned(user.id): return
    
    data = query.data
    if data.startswith("regen_"):
        await query.answer("⏳ Re-generating...")
        parts = data.split("_")
        bin_val = parts[1]
        month = parts[2] if len(parts) > 3 else None
        year = parts[3] if len(parts) > 3 else None
        msg, markup = await process_gen(user, bin_val, month, year)
        try: await query.edit_message_text(msg, reply_markup=markup, parse_mode='HTML')
        except Exception: pass
    elif query.from_user.id == ADMIN_ID:
        if data == "admin_stats":
            total, active, banned, gens = get_detailed_stats()
            stats_msg = (
                f"📊 إحصائيات البوت\n\n"
                f"👥 إجمالي المستخدمين: {total}\n"
                f"✅ نشط: {active}\n"
                f"🚫 محظور: {banned}\n"
                f"🔄 إجمالي التوليدات: {gens}"
            )
            await query.edit_message_text(stats_msg, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]))
        elif data == "admin_backup_file":
            if USERS_JSON.exists():
                await context.bot.send_document(chat_id=ADMIN_ID, document=open(USERS_JSON, 'rb'), filename="users_backup.json", caption="💾 نسخة احتياطية للمشتركين")
            else: await query.answer("❌ لا يوجد بيانات")
        elif data == "admin_recent":
            recent = get_recent_users(10)
            if recent:
                lines = ["👥 آخر 10 مستخدمين:\n"]
                btns = []
                for uid, uname, fname, joined in recent:
                    name_display = f"@{uname}" if uname else fname or str(uid)
                    date_str = joined.strftime("%m/%d %H:%M") if joined else "---"
                    lines.append(f"• {name_display} ({uid}) - {date_str}")
                    if uid != ADMIN_ID:
                        btns.append([InlineKeyboardButton(f"🚫 حظر {name_display}", callback_data=f"ban_{uid}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
                msg_text = "\n".join(lines)
            else:
                msg_text = "لا يوجد مستخدمين بعد."
                btns = [[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]
            await query.edit_message_text(msg_text, reply_markup=InlineKeyboardMarkup(btns))
        elif data == "admin_ban_list":
            banned_list = get_banned_users()
            if banned_list:
                lines = ["🚫 المستخدمين المحظورين:\n"]
                btns = []
                for uid, uname, fname in banned_list:
                    name_display = f"@{uname}" if uname else fname or str(uid)
                    lines.append(f"• {name_display} ({uid})")
                    btns.append([InlineKeyboardButton(f"فك حظر {name_display}", callback_data=f"unban_{uid}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
                await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
            else:
                await query.edit_message_text("لا يوجد مستخدمين محظورين.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]))
        elif data.startswith("ban_") and not data.startswith("ban_list"):
            target_id = int(data.split("_")[1])
            if set_ban_status(target_id, True):
                await query.answer(f"🚫 تم حظر {target_id}", show_alert=True)
            recent = get_recent_users(10)
            if recent:
                lines = ["👥 آخر 10 مستخدمين:\n"]
                btns = []
                for uid, uname, fname, joined in recent:
                    name_display = f"@{uname}" if uname else fname or str(uid)
                    date_str = joined.strftime("%m/%d %H:%M") if joined else "---"
                    lines.append(f"• {name_display} ({uid}) - {date_str}")
                    if uid != ADMIN_ID:
                        btns.append([InlineKeyboardButton(f"🚫 حظر {name_display}", callback_data=f"ban_{uid}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
                await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
        elif data.startswith("unban_"):
            target_id = int(data.split("_")[1])
            if set_ban_status(target_id, False):
                await query.answer(f"تم فك حظر {target_id}", show_alert=True)
            banned_list = get_banned_users()
            if banned_list:
                lines = ["🚫 المستخدمين المحظورين:\n"]
                btns = []
                for uid, uname, fname in banned_list:
                    name_display = f"@{uname}" if uname else fname or str(uid)
                    lines.append(f"• {name_display} ({uid})")
                    btns.append([InlineKeyboardButton(f"فك حظر {name_display}", callback_data=f"unban_{uid}")])
                btns.append([InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")])
                await query.edit_message_text("\n".join(lines), reply_markup=InlineKeyboardMarkup(btns))
            else:
                await query.edit_message_text("لا يوجد مستخدمين محظورين.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]))
        elif data == "admin_broadcast":
            await query.edit_message_text("أرسل: /broadcast <الرسالة>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 رجوع", callback_data="admin_back")]]))
        elif data == "admin_back":
            total, active, banned, gens = get_detailed_stats()
            keyboard = [
                [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
                [InlineKeyboardButton("👥 آخر المستخدمين", callback_data="admin_recent")],
                [InlineKeyboardButton("🚫 قائمة المحظورين", callback_data="admin_ban_list")],
                [InlineKeyboardButton("📢 إذاعة", callback_data="admin_broadcast")],
                [InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup_file")],
            ]
            msg = (
                f"🛠 لوحة تحكم المدير:\n\n"
                f"👥 إجمالي المشتركين: {total}\n"
                f"🔄 إجمالي التوليدات: {gens}"
            )
            await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))

async def forward_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not ADMIN_ID or not update.message: return
    user = update.message.from_user
    if not user or user.id == ADMIN_ID: return
    try:
        name = f"@{user.username}" if user.username else user.first_name or str(user.id)
        text = update.message.text or ""
        log_msg = f"📩 رسالة من {name} ({user.id}):\n\n{text}"
        await context.bot.send_message(chat_id=ADMIN_ID, text=log_msg)
    except Exception:
        pass

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text: return
    if is_user_banned(update.message.from_user.id): return

    await forward_to_admin(update, context)
    
    if country_autodetect:
        handled = await country_autodetect.country_handler(update, context)
        if handled:
            return
    
    await update.message.reply_text("/gen <BIN>  ادخل معلومات البطاقة كالتالي\n\nDDXSTORE")

async def post_init(application):
    init_db()
    await application.bot.set_my_commands([
        BotCommand("start", "ابدأ"),
        BotCommand("gen", "توليد بطاقات"),
        BotCommand("help", "المساعدة"),
    ])

def main():
    if not BOT_TOKEN: return
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("ban", ban_command))
    app.add_handler(CommandHandler("unban", unban_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Regex(r'^/gen\d+'), gen_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))
    
    print("Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
