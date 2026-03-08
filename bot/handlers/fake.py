import random
import string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from bot.database.queries import is_user_banned, increment_request_count, increment_request_stat
from bot.database.bin_db import log_request
from bot.utils.rate_limiter import check_rate_limit, check_flood
from bot.services.i18n import MSG_BANNED, MSG_RATE_LIMIT, MSG_FLOOD, BTN_GENERATE_AGAIN
from bot.services.country_service import (
    FIRST_NAMES_MALE, FIRST_NAMES_FEMALE, LAST_NAMES,
    generate_zip, CITY_DATA,
)

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


def generate_fake_identity():
    first_names = FIRST_NAMES_MALE + FIRST_NAMES_FEMALE
    first = random.choice(first_names)
    last = random.choice(LAST_NAMES)

    countries = list(CITY_DATA.keys())
    country = random.choice(countries)
    data = CITY_DATA[country]
    city = random.choice(data["cities"])
    street_num = random.randint(1, 999)
    street = random.choice(data["streets"])
    state = random.choice(data.get("states", data["districts"]))
    zipcode = generate_zip(data["zip_format"])

    return {
        "name": f"{first} {last}",
        "email": generate_email(first, last),
        "password": generate_password(),
        "dob": generate_dob(),
        "ssn": generate_ssn(),
        "phone": generate_phone_number(),
        "country": country,
        "city": city,
        "street": f"{street_num} {street}",
        "state": state,
        "zip": zipcode,
        "ip": generate_ip(),
        "useragent": random.choice(USER_AGENTS),
    }


def build_fake_msg(fake):
    return (
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"   \U0001f464  DDXSTORE \u2014 Fake ID\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f464  Name     \u2502  {fake['name']}\n"
        f"\U0001f4e7  Email    \u2502  {fake['email']}\n"
        f"\U0001f512  Pass     \u2502  {fake['password']}\n"
        f"\U0001f382  DOB      \u2502  {fake['dob']}\n"
        f"\U0001f4c4  SSN      \u2502  {fake['ssn']}\n"
        f"\u260e  Phone    \u2502  {fake['phone']}\n\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f30d  Country  \u2502  {fake['country']}\n"
        f"\U0001f3d9  City     \u2502  {fake['city']}\n"
        f"\U0001f3e0  Street   \u2502  {fake['street']}\n"
        f"\U0001f4cd  State    \u2502  {fake['state']}\n"
        f"\U0001f4ee  ZIP      \u2502  {fake['zip']}\n\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        f"\U0001f310  IP       \u2502  {fake['ip']}\n"
        f"\U0001f4bb  UA       \u2502  {fake['useragent']}\n\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n"
        f"   \u00a9 DDXSTORE \u2022 @ddx22\n"
        f"\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500"
    )


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
    log_request(user.id, "fake", "")

    fake = generate_fake_identity()
    msg = build_fake_msg(fake)
    keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data="fake_regen")]]
    await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))


async def fake_regen_callback(query, user):
    fake = generate_fake_identity()
    msg = build_fake_msg(fake)
    keyboard = [[InlineKeyboardButton(BTN_GENERATE_AGAIN, callback_data="fake_regen")]]
    try:
        await query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception:
        pass
