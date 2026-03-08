import re
import time
import random
import httpx
from difflib import SequenceMatcher
from bot.config.settings import COUNTRIES_API_URL, COUNTRIES_CACHE_TTL

CITY_DATA = {
    "Saudi Arabia": {
        "cities": ["الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة", "الخبر", "أبها", "تبوك"],
        "districts": ["النخيل", "العليا", "الياسمين", "الروضة", "الشاطئ", "النسيم", "الملز", "الحمراء", "النهضة"],
        "streets": ["طريق الملك فهد", "شارع التحلية", "طريق الملك عبدالله", "شارع الأمير سلطان", "طريق خريص"],
        "zip_format": "1####",
        "phone_code": "+966", "currency": "SAR", "continent": "Asia",
    },
    "United Arab Emirates": {
        "cities": ["دبي", "أبوظبي", "الشارقة", "العين", "عجمان", "رأس الخيمة"],
        "districts": ["المرسى (Marina)", "وسط المدينة (Downtown)", "جميرا", "الخالدية", "القصباء", "خليفة"],
        "streets": ["شارع الشيخ زايد", "طريق الكورنيش", "شارع الوحدة", "شارع حصة", "شارع المطار"],
        "zip_format": "####",
        "phone_code": "+971", "currency": "AED", "continent": "Asia",
    },
    "Egypt": {
        "cities": ["القاهرة", "الإسكندرية", "الجيزة", "المنصورة", "شرم الشيخ", "الأقصر"],
        "districts": ["المعادي", "الزمالك", "مصر الجديدة", "سموحة", "المهندسين", "الدقي", "التجمع الخامس"],
        "streets": ["شارع التسعين", "كورنيش النيل", "شارع فؤاد", "شارع الهرم", "شارع قصر النيل"],
        "zip_format": "#####",
        "phone_code": "+20", "currency": "EGP", "continent": "Africa",
    },
    "Kuwait": {
        "cities": ["مدينة الكويت", "السالمية", "حولي", "الفروانية", "الجهراء"],
        "districts": ["بيان", "مشرف", "الجابرية", "الرميثية", "المنصورية", "الخالدية"],
        "streets": ["شارع الخليج العربي", "طريق الفحيحيل", "شارع سالم المبارك", "طريق الدائري الرابع"],
        "zip_format": "#####",
        "phone_code": "+965", "currency": "KWD", "continent": "Asia",
    },
    "Qatar": {
        "cities": ["الدوحة", "الريان", "الوكرة", "الخور", "لوسيل"],
        "districts": ["اللؤلؤة (The Pearl)", "الدفنة", "مشيرب", "السد", "الوعب"],
        "streets": ["كورنيش الدوحة", "شارع الوعب", "طريق سلوى", "شارع لوسيل الرئيسي"],
        "zip_format": "####",
        "phone_code": "+974", "currency": "QAR", "continent": "Asia",
    },
    "Bahrain": {
        "cities": ["المنامة", "المحرق", "الرفاع", "مدينة حمد", "مدينة عيسى"],
        "districts": ["الجفير", "السيف", "الحورة", "البديع", "العدلية"],
        "streets": ["شارع الملك فيصل", "طريق الشيخ عيسى", "شارع المعارض", "طريق البديع"],
        "zip_format": "####",
        "phone_code": "+973", "currency": "BHD", "continent": "Asia",
    },
    "Oman": {
        "cities": ["مسقط", "صلالة", "صحار", "نزوى", "صور"],
        "districts": ["القرم", "الخوير", "روي", "المعبيلة", "بوشر"],
        "streets": ["شارع السلطان قابوس", "طريق المطار", "شارع المينا", "طريق مسقط السريع"],
        "zip_format": "###",
        "phone_code": "+968", "currency": "OMR", "continent": "Asia",
    },
    "Jordan": {
        "cities": ["عمان", "إربد", "الزرقاء", "العقبة", "مادبا"],
        "districts": ["عبدون", "الشميساني", "جبل عمان", "تلاع العلي", "الصويفية"],
        "streets": ["شارع المدينة المنورة", "شارع مكة", "شارع الجامعة", "طريق المطار"],
        "zip_format": "#####",
        "phone_code": "+962", "currency": "JOD", "continent": "Asia",
    },
    "Iraq": {
        "cities": ["بغداد", "أربيل", "البصرة", "النجف", "كربلاء"],
        "districts": ["المنصور", "الكرادة", "زيونة", "الأعظمية", "الكاظمية"],
        "streets": ["شارع فلسطين", "شارع الرشيد", "طريق المطار", "شارع أبو نواس"],
        "zip_format": "#####",
        "phone_code": "+964", "currency": "IQD", "continent": "Asia",
    },
    "Lebanon": {
        "cities": ["بيروت", "طرابلس", "صيدا", "جبيل", "جونية"],
        "districts": ["الحمرا", "الأشرفية", "فردان", "الجميزة", "الروشة"],
        "streets": ["شارع الحمرا", "طريق الشام", "شارع فردان", "كورنيش بيروت"],
        "zip_format": "#### ####",
        "phone_code": "+961", "currency": "LBP", "continent": "Asia",
    },
    "Morocco": {
        "cities": ["الرباط", "الدار البيضاء", "مراكش", "فاس", "طنجة"],
        "districts": ["أكدال", "حسان", "المعاريف", "جيليز", "القصبة"],
        "streets": ["شارع محمد الخامس", "شارع الحسن الثاني", "طريق المطار"],
        "zip_format": "#####",
        "phone_code": "+212", "currency": "MAD", "continent": "Africa",
    },
    "Algeria": {
        "cities": ["الجزائر العاصمة", "وهران", "قسنطينة", "عنابة", "باتنة"],
        "districts": ["باب الزوار", "الحراش", "حيدرة", "بئر مراد رايس"],
        "streets": ["شارع ديدوش مراد", "شارع العربي بن مهيدي", "طريق المطار"],
        "zip_format": "#####",
        "phone_code": "+213", "currency": "DZD", "continent": "Africa",
    },
    "Tunisia": {
        "cities": ["تونس العاصمة", "صفاقس", "سوسة", "قابس", "بنزرت"],
        "districts": ["المرسى", "قرطاج", "المنزه", "حلق الوادي"],
        "streets": ["شارع الحبيب بورقيبة", "شارع الحرية", "طريق المرسى"],
        "zip_format": "####",
        "phone_code": "+216", "currency": "TND", "continent": "Africa",
    },
    "United States": {
        "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Las Vegas", "San Francisco"],
        "districts": ["Manhattan", "Brooklyn", "Hollywood", "Downtown", "South Beach", "Lincoln Park"],
        "streets": ["5th Avenue", "Broadway", "Sunset Blvd", "Michigan Ave", "Ocean Drive", "Main St"],
        "zip_format": "#####",
        "states": ["NY", "CA", "IL", "TX", "FL", "NV"],
        "phone_code": "+1", "currency": "USD", "continent": "North America",
    },
    "United Kingdom": {
        "cities": ["London", "Manchester", "Birmingham", "Liverpool", "Edinburgh", "Glasgow"],
        "districts": ["Westminster", "Chelsea", "Soho", "Kensington", "Camden Town", "Greenwich"],
        "streets": ["Oxford Street", "Regent St", "Piccadilly", "Abbey Road", "Victoria St"],
        "zip_format": "??# #??",
        "phone_code": "+44", "currency": "GBP", "continent": "Europe",
    },
    "France": {
        "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
        "districts": ["Champs-Elysees", "Montmartre", "Le Marais", "Saint-Germain"],
        "streets": ["Avenue des Champs-Elysees", "Rue de Rivoli", "Boulevard Saint-Germain"],
        "zip_format": "#####",
        "phone_code": "+33", "currency": "EUR", "continent": "Europe",
    },
    "Germany": {
        "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
        "districts": ["Mitte", "Kreuzberg", "Schwabing", "Altstadt"],
        "streets": ["Unter den Linden", "Kurfuerstendamm", "Friedrichstrasse"],
        "zip_format": "#####",
        "phone_code": "+49", "currency": "EUR", "continent": "Europe",
    },
    "Turkey": {
        "cities": ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa"],
        "districts": ["Besiktas", "Sisli", "Kadikoy", "Cankaya", "Konak", "Muratpasa"],
        "streets": ["Istiklal Caddesi", "Bagdat Caddesi", "Ataturk Bulvari", "Cumhuriyet Cad"],
        "zip_format": "#####",
        "phone_code": "+90", "currency": "TRY", "continent": "Asia/Europe",
    },
    "India": {
        "cities": ["New Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata"],
        "districts": ["Connaught Place", "Bandra", "Koramangala", "T. Nagar"],
        "streets": ["MG Road", "Marine Drive", "Nehru Place", "Park Street"],
        "zip_format": "######",
        "phone_code": "+91", "currency": "INR", "continent": "Asia",
    },
    "China": {
        "cities": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu"],
        "districts": ["Chaoyang", "Pudong", "Tianhe", "Nanshan"],
        "streets": ["Chang'an Avenue", "Nanjing Road", "Zhongshan Road"],
        "zip_format": "######",
        "phone_code": "+86", "currency": "CNY", "continent": "Asia",
    },
    "Japan": {
        "cities": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"],
        "districts": ["Shibuya", "Shinjuku", "Ginza", "Minato"],
        "streets": ["Meiji-dori", "Omotesando", "Chuo-dori"],
        "zip_format": "###-####",
        "phone_code": "+81", "currency": "JPY", "continent": "Asia",
    },
    "Brazil": {
        "cities": ["Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador"],
        "districts": ["Copacabana", "Ipanema", "Centro", "Jardins"],
        "streets": ["Av. Paulista", "Av. Atlantica", "Rua Oscar Freire"],
        "zip_format": "#####-###",
        "phone_code": "+55", "currency": "BRL", "continent": "South America",
    },
    "Canada": {
        "cities": ["Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary"],
        "districts": ["Downtown", "Yorkville", "Gastown", "Old Montreal"],
        "streets": ["Yonge Street", "Robson Street", "Rue Sainte-Catherine"],
        "zip_format": "?#? #?#",
        "phone_code": "+1", "currency": "CAD", "continent": "North America",
    },
    "Australia": {
        "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
        "districts": ["CBD", "Bondi", "Southbank", "Surfers Paradise"],
        "streets": ["George Street", "Collins Street", "Queen Street"],
        "zip_format": "####",
        "phone_code": "+61", "currency": "AUD", "continent": "Oceania",
    },
    "Russia": {
        "cities": ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk"],
        "districts": ["Arbat", "Nevsky", "Kremlin District", "Kitay-Gorod"],
        "streets": ["Tverskaya Street", "Nevsky Prospekt", "Arbat Street"],
        "zip_format": "######",
        "phone_code": "+7", "currency": "RUB", "continent": "Europe/Asia",
    },
    "South Korea": {
        "cities": ["Seoul", "Busan", "Incheon", "Daegu"],
        "districts": ["Gangnam", "Myeongdong", "Hongdae", "Itaewon"],
        "streets": ["Gangnam-daero", "Sejong-daero", "Teheran-ro"],
        "zip_format": "#####",
        "phone_code": "+82", "currency": "KRW", "continent": "Asia",
    },
    "Mexico": {
        "cities": ["Mexico City", "Guadalajara", "Monterrey", "Cancun"],
        "districts": ["Polanco", "Condesa", "Roma Norte", "Centro Historico"],
        "streets": ["Av. Reforma", "Av. Insurgentes", "Av. Chapultepec"],
        "zip_format": "#####",
        "phone_code": "+52", "currency": "MXN", "continent": "North America",
    },
    "Spain": {
        "cities": ["Madrid", "Barcelona", "Valencia", "Seville"],
        "districts": ["Salamanca", "Eixample", "El Born", "Triana"],
        "streets": ["Gran Via", "La Rambla", "Paseo de la Castellana"],
        "zip_format": "#####",
        "phone_code": "+34", "currency": "EUR", "continent": "Europe",
    },
    "Italy": {
        "cities": ["Rome", "Milan", "Florence", "Naples", "Venice"],
        "districts": ["Trastevere", "Brera", "San Marco", "Centro Storico"],
        "streets": ["Via del Corso", "Via Montenapoleone", "Via Roma"],
        "zip_format": "#####",
        "phone_code": "+39", "currency": "EUR", "continent": "Europe",
    },
}

GLOBAL_STREETS = ["Main St", "High St", "Park Ave", "Second St", "Broadway", "Oak St", "Maple Ave", "Victoria Rd"]
GLOBAL_DISTRICTS = ["Downtown", "Central District", "North Side", "West End", "Old Town", "Business District"]

ARABIC_COUNTRY_MAP = {
    "السعودية": "saudi arabia", "المملكة العربية السعودية": "saudi arabia",
    "مصر": "egypt", "الامارات": "united arab emirates", "الإمارات": "united arab emirates",
    "الكويت": "kuwait", "قطر": "qatar", "البحرين": "bahrain",
    "عمان": "oman", "سلطنة عمان": "oman", "الاردن": "jordan", "الأردن": "jordan",
    "العراق": "iraq", "سوريا": "syria", "لبنان": "lebanon",
    "فلسطين": "palestine", "اليمن": "yemen", "ليبيا": "libya",
    "تونس": "tunisia", "الجزائر": "algeria", "المغرب": "morocco",
    "السودان": "sudan", "الصومال": "somalia", "جيبوتي": "djibouti", "موريتانيا": "mauritania",
    "تركيا": "turkey", "ايران": "iran", "إيران": "iran",
    "باكستان": "pakistan", "افغانستان": "afghanistan", "أفغانستان": "afghanistan",
    "الهند": "india", "الصين": "china", "اليابان": "japan",
    "كوريا": "south korea", "كوريا الجنوبية": "south korea", "كوريا الشمالية": "north korea",
    "اندونيسيا": "indonesia", "إندونيسيا": "indonesia", "ماليزيا": "malaysia",
    "تايلاند": "thailand", "فيتنام": "vietnam", "الفلبين": "philippines",
    "بنغلاديش": "bangladesh", "سريلانكا": "sri lanka", "نيبال": "nepal",
    "بريطانيا": "united kingdom", "انجلترا": "united kingdom", "إنجلترا": "united kingdom",
    "فرنسا": "france", "المانيا": "germany", "ألمانيا": "germany",
    "ايطاليا": "italy", "إيطاليا": "italy", "اسبانيا": "spain", "إسبانيا": "spain",
    "البرتغال": "portugal", "هولندا": "netherlands", "بلجيكا": "belgium",
    "سويسرا": "switzerland", "النمسا": "austria", "السويد": "sweden",
    "النرويج": "norway", "الدنمارك": "denmark", "فنلندا": "finland",
    "بولندا": "poland", "التشيك": "czechia", "رومانيا": "romania",
    "اليونان": "greece", "روسيا": "russia", "اوكرانيا": "ukraine", "أوكرانيا": "ukraine",
    "امريكا": "united states", "أمريكا": "united states", "الولايات المتحدة": "united states",
    "كندا": "canada", "المكسيك": "mexico", "البرازيل": "brazil",
    "الارجنتين": "argentina", "الأرجنتين": "argentina", "كولومبيا": "colombia",
    "تشيلي": "chile", "بيرو": "peru", "استراليا": "australia", "أستراليا": "australia",
    "نيوزيلندا": "new zealand", "جنوب افريقيا": "south africa", "جنوب أفريقيا": "south africa",
    "نيجيريا": "nigeria", "كينيا": "kenya", "اثيوبيا": "ethiopia", "إثيوبيا": "ethiopia",
    "غانا": "ghana", "تنزانيا": "tanzania", "سنغافورة": "singapore", "تايوان": "taiwan",
}

ENGLISH_ALIASES = {
    "us": "united states", "usa": "united states", "america": "united states",
    "uk": "united kingdom", "england": "united kingdom", "britain": "united kingdom",
    "uae": "united arab emirates", "emirates": "united arab emirates",
    "ksa": "saudi arabia", "saudi": "saudi arabia",
    "korea": "south korea", "sk": "south korea",
}

FIRST_NAMES_MALE = [
    "James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Charles", "Daniel", "Matthew", "Anthony", "Mark", "Christopher",
    "Steven", "Andrew", "Kevin", "Brian", "George", "Edward", "Ronald", "Jason",
    "Ryan", "Jacob", "Nathan", "Samuel", "Benjamin", "Alexander", "Henry",
    "Ethan", "Logan", "Lucas", "Mason", "Oliver", "Liam", "Noah", "Elijah",
]
FIRST_NAMES_FEMALE = [
    "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Susan", "Jessica",
    "Sarah", "Karen", "Lisa", "Nancy", "Betty", "Margaret", "Sandra", "Ashley",
    "Emily", "Donna", "Michelle", "Carol", "Amanda", "Melissa", "Stephanie",
    "Rebecca", "Sharon", "Laura", "Cynthia", "Dorothy", "Amy", "Angela",
    "Olivia", "Emma", "Sophia", "Isabella", "Mia", "Charlotte", "Amelia",
]
LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis",
    "Rodriguez", "Martinez", "Wilson", "Anderson", "Taylor", "Thomas", "Moore",
    "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Clark",
    "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright", "Scott",
    "Hill", "Green", "Adams", "Baker", "Nelson", "Carter", "Mitchell", "Roberts",
    "Turner", "Phillips", "Campbell", "Parker", "Evans", "Edwards", "Collins",
]

_countries_cache = {"data": None, "timestamp": 0}


async def load_countries_cache():
    now = time.time()
    if _countries_cache["data"] and (now - _countries_cache["timestamp"]) < COUNTRIES_CACHE_TTL:
        return _countries_cache["data"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{COUNTRIES_API_URL}?fields=name,translations,cca2,capital,currencies,idd,region")
        if resp.status_code == 200:
            lookup = {}
            for c in resp.json():
                name = c.get("name", {}).get("common", "")
                ara = c.get("translations", {}).get("ara", {}).get("common", "")
                capital_list = c.get("capital", [])
                capital = capital_list[0] if capital_list else ""
                currencies = c.get("currencies", {})
                currency_code = list(currencies.keys())[0] if currencies else ""
                currency_name = currencies.get(currency_code, {}).get("name", "") if currency_code else ""
                idd = c.get("idd", {})
                phone_root = idd.get("root", "")
                phone_suffixes = idd.get("suffixes", [])
                phone_code = phone_root + (phone_suffixes[0] if phone_suffixes else "")
                region = c.get("region", "")
                info = {
                    "name": name, "ara": ara, "cca2": c.get("cca2", ""),
                    "capital": capital, "currency_code": currency_code,
                    "currency_name": currency_name, "phone_code": phone_code,
                    "continent": region,
                }
                lookup[name.lower()] = info
                if ara:
                    lookup[ara] = info
            _countries_cache["data"] = lookup
            _countries_cache["timestamp"] = now
            return lookup
    except Exception:
        pass
    return _countries_cache["data"] or {}


def generate_zip(fmt):
    res = ""
    for char in fmt:
        if char == "#":
            res += str(random.randint(0, 9))
        elif char == "?":
            res += random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        else:
            res += char
    return res


def generate_phone(phone_code):
    if not phone_code:
        phone_code = "+1"
    digits = "".join(str(random.randint(0, 9)) for _ in range(7))
    return f"{phone_code} {digits[:3]}-{digits[3:]}"


def generate_full_name():
    first_names = FIRST_NAMES_MALE + FIRST_NAMES_FEMALE
    return f"{random.choice(first_names)} {random.choice(LAST_NAMES)}"


def get_random_address(country_name, use_arabic=False):
    data = CITY_DATA.get(country_name)
    if data:
        city = random.choice(data["cities"])
        district = random.choice(data["districts"])
        street = random.choice(data["streets"])
        postal = generate_zip(data["zip_format"])
        state = random.choice(data.get("states", [district]))
        phone_code = data.get("phone_code", "+1")
    else:
        city = "Capital City"
        district = random.choice(GLOBAL_DISTRICTS)
        street = random.choice(GLOBAL_STREETS)
        postal = generate_zip("#####")
        state = district
        phone_code = "+1"

    building = random.randint(1, 999)
    floor_num = random.randint(1, 15)
    full_name = generate_full_name()
    phone = generate_phone(phone_code)

    if use_arabic:
        addr = f"\u062d\u064a {district}\u060c {street}\u060c \u0645\u0628\u0646\u0649 \u0631\u0642\u0645 {building}\u060c \u0627\u0644\u062f\u0648\u0631 {floor_num}"
    else:
        addr = f"{building} {street}, {district}, Floor {floor_num}"

    return {
        "full_name": full_name,
        "street": f"{building} {street}",
        "city": city,
        "state": state,
        "zip": postal,
        "phone": phone,
        "district": district,
    }


async def find_country(text):
    text_stripped = text.strip()
    text_lower = text_stripped.lower()
    use_arabic = bool(re.search(r"[\u0600-\u06FF]", text_stripped))

    if text_stripped.startswith("/") or len(text_stripped) > 40 or len(text_stripped.split()) > 5:
        return None, use_arabic

    if text_stripped in ARABIC_COUNTRY_MAP:
        mapped = ARABIC_COUNTRY_MAP[text_stripped]
        lookup = await load_countries_cache()
        match = lookup.get(mapped)
        if match:
            return match, use_arabic

    if text_lower in ENGLISH_ALIASES:
        lookup = await load_countries_cache()
        match = lookup.get(ENGLISH_ALIASES[text_lower])
        if match:
            return match, use_arabic

    lookup = await load_countries_cache()
    if not lookup:
        return None, use_arabic

    match = lookup.get(text_lower) or lookup.get(text_stripped)
    if match:
        return match, use_arabic

    best_match, best_ratio = None, 0
    for key in lookup:
        ratio = SequenceMatcher(None, text_lower, key.lower()).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = lookup[key]
    if best_ratio >= 0.90:
        return best_match, use_arabic

    return None, use_arabic


_SEP  = "\u2500" * 11   # ─────────────
_FOOT = "\u00a9 DDXSTORE \u2022 @ddx22"


def _row(label: str, value: str, code: bool = False) -> str:
    val = ("<code>" + value + "</code>") if code else value
    return "<b>" + label + "</b>  :  " + val


def get_country_info_text(match, use_arabic):
    country_name = match["name"]
    capital = match.get("capital", "N/A")

    display_name = (match.get("ara") or country_name) if use_arabic else country_name
    rand_name = generate_full_name()
    addr = get_random_address(country_name, use_arabic)

    lines = [
        "    \U0001f30d  <b>COUNTRY INFO</b>",
        _SEP,
        _row("Name",    rand_name,                       code=True),
        _row("Country", display_name),
        _row("Capital", capital),
        _row("Street",  addr.get("street") or "\u2014",  code=True),
        _row("State",   addr.get("state")  or "\u2014"),
        _row("ZIP",     addr.get("zip")    or "\u2014",  code=True),
        _SEP,
        "    <i>" + _FOOT + "</i>",
    ]
    return "\n".join(lines)


def get_address_text(country_name, use_arabic=False):
    addr  = get_random_address(country_name, use_arabic)
    phone = CITY_DATA.get(country_name, {}).get("phone_code", addr.get("phone", "\u2014"))

    lines = [
        "    \U0001f4cd  <b>ADDRESS GEN</b>",
        _SEP,
        _row("Name",    addr.get("full_name") or "\u2014", code=True),
        _row("Country", country_name),
        _row("City",    addr.get("city")   or "\u2014", code=True),
        _row("Street",  addr.get("street") or "\u2014", code=True),
        _row("State",   addr.get("state")  or "\u2014"),
        _row("ZIP",     addr.get("zip")    or "\u2014", code=True),
        _row("Phone",   phone,                         code=True),
        _SEP,
        "    <i>" + _FOOT + "</i>",
    ]
    return "\n".join(lines)
