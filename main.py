# main.py
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
ADMIN_ID_STR = os.getenv("ADMIN_ID", "331753565")
ADMIN_ID = int(ADMIN_ID_STR) if ADMIN_ID_STR.isdigit() else 0

# [NEW] Backup System for Non-DB environments
DATA_DIR = Path("./data")
DATA_DIR.mkdir(exist_ok=True)
USERS_JSON = DATA_DIR / "users.json"
BACKUP_DIR = Path("./backups")
BACKUP_DIR.mkdir(exist_ok=True)

# --- Backup Helpers ---
def _local_register_user(user_id, username, first_name):
    """حفظ نسخة محلية احتياطية للمشتركين"""
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
            
            # نسخة احتياطية دورية
            timestamp = datetime.now().strftime("%Y%m%d")
            daily_backup = BACKUP_DIR / f"users_backup_{timestamp}.json"
            if not daily_backup.exists():
                daily_backup.write_text(json.dumps(users, ensure_ascii=False), encoding="utf-8")
    except: pass

# --- Database Functions ---

def init_db():
    if not DATABASE_URL: 
        print("⚠️ DATABASE_URL not set. Running in Local Mode.")
        return
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
        print("✅ Database Initialized Successfully.")
    except Exception as e: print(f"DB Init Error: {e}")

def register_user(user_id, username, first_name):
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

def get_detailed_stats():
    if not DATABASE_URL:
        try:
            users = json.loads(USERS_JSON.read_text(encoding="utf-8")) if USERS_JSON.exists() else {}
            return len(users), len(users), 0, 0
        except: return 0, 0, 0, 0
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
        return total, active, banned, gens
    except Exception: return 0, 0, 0, 0

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
                timeout=5
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
    welcome_text = (
        f"مرحبا {user.first_name}! 👋\n\n"
        f"أهلا فيك في بوت DDXSTORE\n\n"
        f"الأوامر المتاحة:\n"
        f"/gen <BIN> - توليد بطاقات\n"
        f"/help - المساعدة\n\n"
        f"جرب الآن: /gen 451014\n\n"
        f"© DDXSTORE"
    )
    await update.message.reply_text(welcome_text)

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or update.message.from_user.id != ADMIN_ID: return
    keyboard = [
        [InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")],
        [InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup")],
    ]
    await update.message.reply_text("🛠 لوحة تحكم المدير:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or query.from_user.id != ADMIN_ID: return
    await query.answer()
    if query.data == "admin_stats":
        t, a, b, g = get_detailed_stats()
        text = f"📊 إحصائيات البوت:\n\n👥 الإجمالي: {t}\n✅ النشطين: {a}\n🚫 المحظورين: {b}\n💳 التوليدات: {g}"
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("رجوع", callback_data="admin_main")]]))
    elif query.data == "admin_backup":
        if USERS_JSON.exists():
            await context.bot.send_document(chat_id=ADMIN_ID, document=open(USERS_JSON, 'rb'), filename="users_backup.json", caption="💾 نسخة احتياطية للمشتركين")
        else: await query.answer("❌ لا يوجد بيانات حالياً")
    elif query.data == "admin_main":
        keyboard = [[InlineKeyboardButton("📊 الإحصائيات", callback_data="admin_stats")], [InlineKeyboardButton("💾 نسخة احتياطية", callback_data="admin_backup")]]
        await query.edit_message_text("🛠 لوحة تحكم المدير:", reply_markup=InlineKeyboardMarkup(keyboard))

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message: return
    user_id = update.message.from_user.id
    if is_user_banned(user_id): return
    args = context.args
    if not args:
        await update.message.reply_text("❌ يرجى إدخال BIN\nمثال: `/gen 451014`", parse_mode='Markdown')
        return
    
    bin_input = args[0]
    prefix = re.sub(r'[^0-9]', '', bin_input.split('x')[0] if 'x' in bin_input.lower() else bin_input)
    if len(prefix) < 6:
        await update.message.reply_text("❌ الـ BIN يجب أن يكون 6 أرقام على الأقل.")
        return

    wait_msg = await update.message.reply_text("⏳ جاري التوليد والبحث...")
    scheme, card_type, bank, country, emoji = await bin_lookup(prefix[:6])
    
    cards = []
    for _ in range(10):
        cc = generate_card_from_prefix(prefix)
        mm, yy = generate_expiry()
        cvv = generate_cvv()
        cards.append(f"<code>{cc}|{mm}|{yy}|{cvv}</code>")
    
    # استخدام خاصية تحديد الدولة تلقائياً إذا كانت متوفرة
    extra_info = ""
    if country_autodetect and country != "N/A":
        addr = country_autodetect.get_random_address(country)
        if addr:
            extra_info = f"\n\n📍 **معلومات العنوان المقترحة:**\n🏙 المدينة: {addr['city']}\n🏘 الحي: {addr['district']}\n🛣 الشارع: {addr['street']}\n📮 الرمز البريدي: {addr['zip']}"

    response = (
        f"✅ **تم التوليد بنجاح!**\n\n"
        f"🔹 **المعلومات:** {scheme} - {card_type}\n"
        f"🏛 **البنك:** {bank}\n"
        f"🌍 **الدولة:** {country} {emoji}\n\n"
        f"💳 **البطاقات:**\n" + "\n".join(cards) +
        f"{extra_info}\n\n"
        f"© DDXSTORE"
    )
    
    increment_gen_stat()
    await wait_msg.delete()
    await update.message.reply_text(response, parse_mode='HTML')

def main():
    if not BOT_TOKEN: return
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("gen", gen_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    print("🚀 البوت الثاني يعمل الآن...")
    app.run_polling()

if __name__ == "__main__":
    main()
