import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.services.i18n import MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD, BTN_GENERATE_AGAIN
from bot.utils.formatter import fake_msg
from bot.services.country_service import (
    FIRST_NAMES_MALE, FIRST_NAMES_FEMALE, LAST_NAMES,
    generate_zip, CITY_DATA, generate_phone, _get_flag,
)
from bot.utils.logger import get_logger

logger = get_logger("fake")

COUNTRY_MAP = {
    "us": "United States",   "usa": "United States",   "america": "United States",
    "uk": "United Kingdom",  "gb": "United Kingdom",   "britain": "United Kingdom",
    "sa": "Saudi Arabia",    "ksa": "Saudi Arabia",    "saudi": "Saudi Arabia",
    "ae": "United Arab Emirates", "uae": "United Arab Emirates", "emirates": "United Arab Emirates",
    "eg": "Egypt",           "egypt": "Egypt",
    "kw": "Kuwait",          "kuwait": "Kuwait",
    "qa": "Qatar",           "qatar": "Qatar",
    "bh": "Bahrain",         "bahrain": "Bahrain",
    "om": "Oman",            "oman": "Oman",
    "jo": "Jordan",          "jordan": "Jordan",
    "iq": "Iraq",            "iraq": "Iraq",
    "lb": "Lebanon",         "lebanon": "Lebanon",
    "ma": "Morocco",         "morocco": "Morocco",
    "dz": "Algeria",         "algeria": "Algeria",
    "tn": "Tunisia",         "tunisia": "Tunisia",
    "fr": "France",          "france": "France",
    "de": "Germany",         "germany": "Germany",
    "tr": "Turkey",          "turkey": "Turkey",
    "in": "India",           "india": "India",
    "cn": "China",           "china": "China",
    "jp": "Japan",           "japan": "Japan",
    "br": "Brazil",          "brazil": "Brazil",
    "ca": "Canada",          "canada": "Canada",
    "au": "Australia",       "australia": "Australia",
    "ru": "Russia",          "russia": "Russia",
    "kr": "South Korea",     "korea": "South Korea",   "sk": "South Korea",
    "mx": "Mexico",          "mexico": "Mexico",
    "es": "Spain",           "spain": "Spain",
    "it": "Italy",           "italy": "Italy",
}

DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com", "icloud.com"]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Mobile/15E148",
    "Mozilla/5.0 (Linux; Android 14) Chrome/120.0.6099.43",
    "Mozilla/5.0 (X11; Linux x86_64) Firefox/120.0",
]


def generate_email(first, last):
    sep = random.choice([".", "_", ""])
    num = random.randint(1, 999)
    domain = random.choice(DOMAINS)
    return f"{first.lower()}{sep}{last.lower()}{num}@{domain}"


def generate_password():
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    return "".join(random.choices(chars, k=random.randint(12, 16)))


def generate_ip():
    return f"{random.randint(1,223)}.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}"


def generate_ssn():
    return f"{random.randint(100,999)}-{random.randint(10,99)}-{random.randint(1000,9999)}"


def generate_dob():
    year = random.randint(1970, 2003)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"{month:02d}/{day:02d}/{year}"


def generate_phone_number():
    area = random.randint(200, 999)
    mid = random.randint(200, 999)
    end = random.randint(1000, 9999)
    return f"+1 ({area}) {mid}-{end}"


def resolve_country(query: str) -> str | None:
    if not query:
        return None
    q = query.strip().lower()
    if q in COUNTRY_MAP:
        return COUNTRY_MAP[q]
    for key in CITY_DATA:
        if key.lower() == q:
            return key
    for key in CITY_DATA:
        if key.lower().startswith(q):
            return key
    return None


def generate_fake_identity(country: str = None):
    first_names = FIRST_NAMES_MALE + FIRST_NAMES_FEMALE
    first = random.choice(first_names)
    last = random.choice(LAST_NAMES)

    countries = list(CITY_DATA.keys())
    country = country if (country and country in CITY_DATA) else random.choice(countries)
    data = CITY_DATA[country]
    city = random.choice(data["cities"])
    street_num = random.randint(1, 999)
    street = random.choice(data["streets"])
    state = random.choice(data.get("states", data["districts"]))
    zipcode = generate_zip(data["zip_format"])

    phone_code = data.get("phone_code", "+1")
    gender = random.choice(["Male", "Female"])

    return {
        "name": f"{first} {last}",
        "gender": gender,
        "email": generate_email(first, last),
        "password": generate_password(),
        "dob": generate_dob(),
        "ssn": generate_ssn(),
        "phone": generate_phone(phone_code),
        "country": country,
        "flag": _get_flag(country),
        "city": city,
        "street": f"{street_num} {street}",
        "state": state,
        "zip": zipcode,
        "ip": generate_ip(),
        "useragent": random.choice(USER_AGENTS),
    }


def _make_keyboard(cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data=cb)]])


async def fake_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user = update.message.from_user
    if not user:
        return

    if is_user_banned(user.id):
        await update.message.reply_text(MSG_BANNED)
        return
    if check_flood(user.id):
        await update.message.reply_text(MSG_FLOOD)
        return
    if not check_rate_limit(user.id):
        await update.message.reply_text(MSG_RATE_LIMIT)
        return

    increment_request_count(user.id)
    increment_request_stat()

    country_query = " ".join(context.args) if context.args else None
    resolved = resolve_country(country_query) if country_query else None

    if country_query and not resolved:
        import html as _h
        await update.message.reply_text(
            f"❌ الدولة '{_h.escape(country_query)}' غير موجودة.\n\n"
            f"أمثلة: /fake us · /fake kr · /fake fr · /fake sa\n"
            f"سيتم توليد هوية عشوائية..."
        )

    log_request(user.id, "fake", resolved or "random")
    logger.info(f"User {user.id} /fake country={resolved or 'random'}")

    fake = generate_fake_identity(resolved)
    msg  = fake_msg(fake)
    cb_country = resolved.replace(" ", "+") if resolved else ""
    cb   = f"fake_regen_{cb_country}" if cb_country else "fake_regen"

    await update.message.reply_text(msg, reply_markup=_make_keyboard(cb), parse_mode="HTML")


async def fake_regen_callback(query, user):
    data = query.data
    country = None
    if data.startswith("fake_regen_"):
        country = data[len("fake_regen_"):].replace("+", " ") or None

    fake = generate_fake_identity(country)
    msg  = fake_msg(fake)
    keyboard = _make_keyboard(data)

    try:
        await query.edit_message_text(msg, reply_markup=keyboard, parse_mode="HTML")
    except Exception as e:
        err = str(e).lower()
        if "message is not modified" in err:
            await query.answer("✅ تم التحديث")
        else:
            logger.warning(f"fake_regen edit failed: {e}")
            try:
                await query.message.delete()
            except Exception:
                pass
            await query.message.reply_text(msg, reply_markup=keyboard, parse_mode="HTML")
