import re
import random
from datetime import datetime
from bot.utils.luhn import calculate_luhn
from bot.config.settings import DEFAULT_CARD_LENGTH


def generate_card_from_prefix(prefix, total_length=DEFAULT_CARD_LENGTH):
    prefix = re.sub(r"[^0-9]", "", str(prefix))
    if not prefix:
        return None
    prefix_length = len(prefix)
    if prefix_length >= total_length:
        prefix = prefix[: total_length - 1]
        prefix_length = total_length - 1
    remaining = total_length - prefix_length - 1
    if remaining < 0:
        return None
    middle_digits = "".join(str(random.randint(0, 9)) for _ in range(remaining))
    partial = prefix + middle_digits
    check = calculate_luhn(int(partial))
    return partial + str(check)


def generate_expiry():
    now = datetime.now()
    future_year = now.year + random.randint(1, 5)
    month = random.randint(1, 12)
    return f"{month:02d}", f"{future_year}"


def generate_cvv():
    return f"{random.randint(0, 999):03d}"


def generate_cards(prefix, count=10, fixed_month=None, fixed_year=None, fixed_cvv=None):
    cards = []
    for _ in range(count):
        card = generate_card_from_prefix(prefix)
        if not card:
            continue
        m, y = (fixed_month, fixed_year) if (fixed_month and fixed_year) else generate_expiry()
        cvv = fixed_cvv if fixed_cvv else generate_cvv()
        cards.append({"number": card, "month": m, "year": y, "cvv": cvv})
    return cards
