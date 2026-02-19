import re
import time
import httpx
import random
from difflib import SequenceMatcher
from telegram import Update
from telegram.ext import ContextTypes

CITY_DATA = {
    "Saudi Arabia": {
        "cities": ["الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة", "الخبر", "أبها", "تبوك"],
        "districts": ["النخيل", "العليا", "الياسمين", "الروضة", "الشاطئ", "النسيم", "الملز", "الحمراء", "النهضة"],
        "streets": ["طريق الملك فهد", "شارع التحلية", "طريق الملك عبدالله", "شارع الأمير سلطان", "طريق خريص"],
        "zip_format": "1####"
    },
    "United Arab Emirates": {
        "cities": ["دبي", "أبوظبي", "الشارقة", "العين", "عجمان", "رأس الخيمة"],
        "districts": ["المرسى (Marina)", "وسط المدينة (Downtown)", "جميرا", "الخالدية", "القصباء", "خليفة"],
        "streets": ["شارع الشيخ زايد", "طريق الكورنيش", "شارع الوحدة", "شارع حصة", "شارع المطار"],
        "zip_format": "####"
    },
    "Egypt": {
        "cities": ["القاهرة", "الإسكندرية", "الجيزة", "المنصورة", "شرم الشيخ", "الأقصر"],
        "districts": ["المعادي", "الزمالك", "مصر الجديدة", "سموحة", "المهندسين", "الدقي", "التجمع الخامس"],
        "streets": ["شارع التسعين", "كورنيش النيل", "شارع فؤاد", "شارع الهرم", "شارع قصر النيل"],
        "zip_format": "#####"
    },
    "Kuwait": {
        "cities": ["مدينة الكويت", "السالمية", "حولي", "الفروانية", "الجهراء"],
        "districts": ["بيان", "مشرف", "الجابرية", "الرميثية", "المنصورية", "الخالدية"],
        "streets": ["شارع الخليج العربي", "طريق الفحيحيل", "شارع سالم المبارك", "طريق الدائري الرابع"],
        "zip_format": "#####"
    },
    "Qatar": {
        "cities": ["الدوحة", "الريان", "الوكرة", "الخور", "لوسيل"],
        "districts": ["اللؤلؤة (The Pearl)", "الدفنة", "مشيرب", "السد", "الوعب"],
        "streets": ["كورنيش الدوحة", "شارع الوعب", "طريق سلوى", "شارع لوسيل الرئيسي"],
        "zip_format": "####"
    },
    "Bahrain": {
        "cities": ["المنامة", "المحرق", "الرفاع", "مدينة حمد", "مدينة عيسى"],
        "districts": ["الجفير", "السيف", "الحورة", "البديع", "العدلية"],
        "streets": ["شارع الملك فيصل", "طريق الشيخ عيسى", "شارع المعارض", "طريق البديع"],
        "zip_format": "####"
    },
    "Oman": {
        "cities": ["مسقط", "صلالة", "صحار", "نزوى", "صور"],
        "districts": ["القرم", "الخوير", "روي", "المعبيلة", "بوشر"],
        "streets": ["شارع السلطان قابوس", "طريق المطار", "شارع المينا", "طريق مسقط السريع"],
        "zip_format": "###"
    },
    "Jordan": {
        "cities": ["عمان", "إربد", "الزرقاء", "العقبة", "مادبا"],
        "districts": ["عبدون", "الشميساني", "جبل عمان", "تلاع العلي", "الصويفية"],
        "streets": ["شارع المدينة المنورة", "شارع مكة", "شارع الجامعة", "طريق المطار"],
        "zip_format": "#####"
    },
    "Iraq": {
        "cities": ["بغداد", "أربيل", "البصرة", "النجف", "كربلاء"],
        "districts": ["المنصور", "الكرادة", "زيونة", "الأعظمية", "الكاظمية"],
        "streets": ["شارع فلسطين", "شارع الرشيد", "طريق المطار", "شارع أبو نواس"],
        "zip_format": "#####"
    },
    "Lebanon": {
        "cities": ["بيروت", "طرابلس", "صيدا", "جبيل", "جونية"],
        "districts": ["الحمرا", "الأشرفية", "فردان", "الجميزة", "الروشة"],
        "streets": ["شارع الحمرا", "طريق الشام", "شارع فردان", "كورنيش بيروت"],
        "zip_format": "#### ####"
    },
    "Morocco": {
        "cities": ["الرباط", "الدار البيضاء", "مراكش", "فاس", "طنجة"],
        "districts": ["أكدال", "حسان", "المعاريف", "جيليز", "القصبة"],
        "streets": ["شارع محمد الخامس", "شارع الحسن الثاني", "طريق المطار"],
        "zip_format": "#####"
    },
    "Algeria": {
        "cities": ["الجزائر العاصمة", "وهران", "قسنطينة", "عنابة", "باتنة"],
        "districts": ["باب الزوار", "الحراش", "حيدرة", "بئر مراد رايس"],
        "streets": ["شارع ديدوش مراد", "شارع العربي بن مهيدي", "طريق المطار"],
        "zip_format": "#####"
    },
    "Tunisia": {
        "cities": ["تونس العاصمة", "صفاقس", "سوسة", "قابس", "بنزرت"],
        "districts": ["المرسى", "قرطاج", "المنزه", "حلق الوادي"],
        "streets": ["شارع الحبيب بورقيبة", "شارع الحرية", "طريق المرسى"],
        "zip_format": "####"
    },
    "United States": {
        "cities": ["New York", "Los Angeles", "Chicago", "Houston", "Miami", "Las Vegas", "San Francisco"],
        "districts": ["Manhattan", "Brooklyn", "Hollywood", "Downtown", "South Beach", "Lincoln Park"],
        "streets": ["5th Avenue", "Broadway", "Sunset Blvd", "Michigan Ave", "Ocean Drive", "Main St"],
        "zip_format": "#####"
    },
    "United Kingdom": {
        "cities": ["London", "Manchester", "Birmingham", "Liverpool", "Edinburgh", "Glasgow"],
        "districts": ["Westminster", "Chelsea", "Soho", "Kensington", "Camden Town", "Greenwich"],
        "streets": ["Oxford Street", "Regent St", "Piccadilly", "Abbey Road", "Victoria St"],
        "zip_format": "??# #??"
    },
    "France": {
        "cities": ["Paris", "Marseille", "Lyon", "Toulouse", "Nice"],
        "districts": ["Champs-Élysées", "Montmartre", "Le Marais", "Saint-Germain"],
        "streets": ["Avenue des Champs-Élysées", "Rue de Rivoli", "Boulevard Saint-Germain"],
        "zip_format": "#####"
    },
    "Germany": {
        "cities": ["Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne"],
        "districts": ["Mitte", "Kreuzberg", "Schwabing", "Altstadt"],
        "streets": ["Unter den Linden", "Kurfürstendamm", "Friedrichstraße"],
        "zip_format": "#####"
    },
    "Turkey": {
        "cities": ["Istanbul", "Ankara", "Izmir", "Antalya", "Bursa"],
        "districts": ["Beşiktaş", "Şişli", "Kadıköy", "Çankaya", "Konak", "Muratpaşa"],
        "streets": ["İstiklal Caddesi", "Bağdat Caddesi", "Atatürk Bulvarı", "Cumhuriyet Cad"],
        "zip_format": "#####"
    },
    "India": {
        "cities": ["New Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata"],
        "districts": ["Connaught Place", "Bandra", "Koramangala", "T. Nagar"],
        "streets": ["MG Road", "Marine Drive", "Nehru Place", "Park Street"],
        "zip_format": "######"
    },
    "China": {
        "cities": ["Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu"],
        "districts": ["Chaoyang", "Pudong", "Tianhe", "Nanshan"],
        "streets": ["Chang'an Avenue", "Nanjing Road", "Zhongshan Road"],
        "zip_format": "######"
    },
    "Japan": {
        "cities": ["Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya"],
        "districts": ["Shibuya", "Shinjuku", "Ginza", "Minato"],
        "streets": ["Meiji-dori", "Omotesando", "Chuo-dori"],
        "zip_format": "###-####"
    },
    "Brazil": {
        "cities": ["São Paulo", "Rio de Janeiro", "Brasília", "Salvador"],
        "districts": ["Copacabana", "Ipanema", "Centro", "Jardins"],
        "streets": ["Av. Paulista", "Av. Atlântica", "Rua Oscar Freire"],
        "zip_format": "#####-###"
    },
    "Canada": {
        "cities": ["Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary"],
        "districts": ["Downtown", "Yorkville", "Gastown", "Old Montreal"],
        "streets": ["Yonge Street", "Robson Street", "Rue Sainte-Catherine"],
        "zip_format": "?#? #?#"
    },
    "Australia": {
        "cities": ["Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide"],
        "districts": ["CBD", "Bondi", "Southbank", "Surfers Paradise"],
        "streets": ["George Street", "Collins Street", "Queen Street"],
        "zip_format": "####"
    },
    "Russia": {
        "cities": ["Moscow", "Saint Petersburg", "Kazan", "Novosibirsk"],
        "districts": ["Arbat", "Nevsky", "Kremlin District", "Kitay-Gorod"],
        "streets": ["Tverskaya Street", "Nevsky Prospekt", "Arbat Street"],
        "zip_format": "######"
    },
    "South Korea": {
        "cities": ["Seoul", "Busan", "Incheon", "Daegu"],
        "districts": ["Gangnam", "Myeongdong", "Hongdae", "Itaewon"],
        "streets": ["Gangnam-daero", "Sejong-daero", "Teheran-ro"],
        "zip_format": "#####"
    },
    "Mexico": {
        "cities": ["Mexico City", "Guadalajara", "Monterrey", "Cancún"],
        "districts": ["Polanco", "Condesa", "Roma Norte", "Centro Histórico"],
        "streets": ["Av. Reforma", "Av. Insurgentes", "Av. Chapultepec"],
        "zip_format": "#####"
    },
    "Spain": {
        "cities": ["Madrid", "Barcelona", "Valencia", "Seville"],
        "districts": ["Salamanca", "Eixample", "El Born", "Triana"],
        "streets": ["Gran Vía", "La Rambla", "Paseo de la Castellana"],
        "zip_format": "#####"
    },
    "Italy": {
        "cities": ["Rome", "Milan", "Florence", "Naples", "Venice"],
        "districts": ["Trastevere", "Brera", "San Marco", "Centro Storico"],
        "streets": ["Via del Corso", "Via Montenapoleone", "Via Roma"],
        "zip_format": "#####"
    },
}

GLOBAL_STREETS = ["Main St", "High St", "Park Ave", "Second St", "Broadway", "Oak St", "Maple Ave", "Victoria Rd"]
GLOBAL_DISTRICTS = ["Downtown", "Central District", "North Side", "West End", "Old Town", "Business District"]

ARABIC_COUNTRY_MAP = {
    "السعودية": "saudi arabia",
    "المملكة العربية السعودية": "saudi arabia",
    "مصر": "egypt",
    "الامارات": "united arab emirates",
    "الإمارات": "united arab emirates",
    "الكويت": "kuwait",
    "قطر": "qatar",
    "البحرين": "bahrain",
    "عمان": "oman",
    "سلطنة عمان": "oman",
    "الاردن": "jordan",
    "الأردن": "jordan",
    "العراق": "iraq",
    "سوريا": "syria",
    "لبنان": "lebanon",
    "فلسطين": "palestine",
    "اليمن": "yemen",
    "ليبيا": "libya",
    "تونس": "tunisia",
    "الجزائر": "algeria",
    "المغرب": "morocco",
    "السودان": "sudan",
    "الصومال": "somalia",
    "جيبوتي": "djibouti",
    "موريتانيا": "mauritania",
    "تركيا": "turkey",
    "ايران": "iran",
    "إيران": "iran",
    "باكستان": "pakistan",
    "افغانستان": "afghanistan",
    "أفغانستان": "afghanistan",
    "الهند": "india",
    "الصين": "china",
    "اليابان": "japan",
    "كوريا": "south korea",
    "كوريا الجنوبية": "south korea",
    "كوريا الشمالية": "north korea",
    "اندونيسيا": "indonesia",
    "إندونيسيا": "indonesia",
    "ماليزيا": "malaysia",
    "تايلاند": "thailand",
    "فيتنام": "vietnam",
    "الفلبين": "philippines",
    "بنغلاديش": "bangladesh",
    "سريلانكا": "sri lanka",
    "نيبال": "nepal",
    "بريطانيا": "united kingdom",
    "انجلترا": "united kingdom",
    "إنجلترا": "united kingdom",
    "فرنسا": "france",
    "المانيا": "germany",
    "ألمانيا": "germany",
    "ايطاليا": "italy",
    "إيطاليا": "italy",
    "اسبانيا": "spain",
    "إسبانيا": "spain",
    "البرتغال": "portugal",
    "هولندا": "netherlands",
    "بلجيكا": "belgium",
    "سويسرا": "switzerland",
    "النمسا": "austria",
    "السويد": "sweden",
    "النرويج": "norway",
    "الدنمارك": "denmark",
    "فنلندا": "finland",
    "بولندا": "poland",
    "التشيك": "czechia",
    "رومانيا": "romania",
    "اليونان": "greece",
    "روسيا": "russia",
    "اوكرانيا": "ukraine",
    "أوكرانيا": "ukraine",
    "امريكا": "united states",
    "أمريكا": "united states",
    "الولايات المتحدة": "united states",
    "كندا": "canada",
    "المكسيك": "mexico",
    "البرازيل": "brazil",
    "الارجنتين": "argentina",
    "الأرجنتين": "argentina",
    "كولومبيا": "colombia",
    "تشيلي": "chile",
    "بيرو": "peru",
    "استراليا": "australia",
    "أستراليا": "australia",
    "نيوزيلندا": "new zealand",
    "جنوب افريقيا": "south africa",
    "جنوب أفريقيا": "south africa",
    "نيجيريا": "nigeria",
    "كينيا": "kenya",
    "اثيوبيا": "ethiopia",
    "إثيوبيا": "ethiopia",
    "غانا": "ghana",
    "تنزانيا": "tanzania",
    "سنغافورة": "singapore",
    "تايوان": "taiwan",
}

COUNTRIES_CACHE = {"data": None, "timestamp": 0}


async def load_countries_cache():
    now = time.time()
    if COUNTRIES_CACHE["data"] and (now - COUNTRIES_CACHE["timestamp"]) < 86400:
        return COUNTRIES_CACHE["data"]
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get("https://restcountries.com/v3.1/all?fields=name,translations,cca2,capital")
        if resp.status_code == 200:
            lookup = {}
            for c in resp.json():
                name = c.get("name", {}).get("common", "")
                ara = c.get("translations", {}).get("ara", {}).get("common", "")
                capital = c.get("capital", [""])[0] if c.get("capital") else ""
                info = {"name": name, "ara": ara, "cca2": c.get("cca2", ""), "capital": capital}
                lookup[name.lower()] = info
                if ara:
                    lookup[ara] = info
            COUNTRIES_CACHE["data"] = lookup
            COUNTRIES_CACHE["timestamp"] = now
            return lookup
    except Exception:
        pass
    return COUNTRIES_CACHE["data"] or {}


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


def get_random_address(country_name, use_arabic):
    data = CITY_DATA.get(country_name)
    if data:
        city = random.choice(data["cities"])
        district = random.choice(data["districts"])
        street = random.choice(data["streets"])
        postal = generate_zip(data["zip_format"])
    else:
        city = "Capital City"
        district = random.choice(GLOBAL_DISTRICTS)
        street = random.choice(GLOBAL_STREETS)
        postal = generate_zip("#####")

    building = random.randint(1, 999)
    floor_num = random.randint(1, 15)

    if use_arabic:
        addr = f"حي {district}، {street}، مبنى رقم {building}، الدور {floor_num}"
    else:
        addr = f"{building} {street}, {district}, Floor {floor_num}"

    return city, addr, postal


async def country_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return False

    text = update.message.text.strip()

    if text.startswith("/") or len(text) > 40 or len(text.split()) > 5:
        return False

    lookup = await load_countries_cache()
    if not lookup:
        return False

    text_lower = text.lower()
    use_arabic = bool(re.search(r'[\u0600-\u06FF]', text))

    match = None

    if text in ARABIC_COUNTRY_MAP:
        mapped = ARABIC_COUNTRY_MAP[text]
        match = lookup.get(mapped)

    if not match:
        match = lookup.get(text_lower)

    if not match:
        match = lookup.get(text)

    if not match:
        best_match, best_ratio = None, 0
        for key in lookup:
            ratio = SequenceMatcher(None, text_lower, key.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = lookup[key]
        if best_ratio >= 0.90:
            match = best_match

    if not match:
        return False

    country_name = match["name"]
    capital = match.get("capital", "")
    city, address, postal = get_random_address(country_name, use_arabic)

    if capital and not CITY_DATA.get(country_name):
        city = capital

    if use_arabic:
        display_name = match.get("ara") or country_name
        msg = (
            f"🌍 نظام المعلومات العالمي\n\n"
            f"🏳️ الدولة: {display_name}\n"
            f"🏙 المدينة: {city}\n"
            f"📍 العنوان: {address}\n"
            f"🧾 الرمز البريدي: {postal}\n\n"
            f"© DDXSTORE"
        )
    else:
        msg = (
            f"🌍 Global Info System\n\n"
            f"🏳️ Country: {country_name}\n"
            f"🏙 City: {city}\n"
            f"📍 Address: {address}\n"
            f"🧾 Zip-code: {postal}\n\n"
            f"© DDXSTORE"
        )

    await update.message.reply_text(msg)
    return True
