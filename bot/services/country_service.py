import re
import time
import random
import httpx
from difflib import SequenceMatcher
from bot.config.settings import COUNTRIES_API_URL, COUNTRIES_CACHE_TTL

CITY_DATA = {
    "Saudi Arabia": {
        "cities": [
            "الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة",
            "الخبر", "أبها", "تبوك", "بريدة", "حائل", "الطائف", "خميس مشيط",
            "الجبيل", "ينبع", "نجران", "الأحساء", "القطيف", "عرعر", "سكاكا",
            "جازان", "الباحة", "الدوادمي", "المجمعة", "رابغ", "وادي الدواسر",
        ],
        "districts": [
            "النخيل", "العليا", "الياسمين", "الروضة", "الشاطئ", "النسيم",
            "الملز", "الحمراء", "النهضة", "السليمانية", "الزهراء", "الريان",
            "المروج", "العقيق", "الوادي", "الصفا", "الربيع", "الربوة",
            "الفيصلية", "السفارات", "الورود", "طويق", "الندى", "القادسية",
        ],
        "streets": [
            "طريق الملك فهد", "شارع التحلية", "طريق الملك عبدالله",
            "شارع الأمير سلطان", "طريق خريص", "طريق الدائري الشمالي",
            "شارع الوزير", "طريق الملك عبدالعزيز", "شارع العروبة",
            "طريق مكة المكرمة", "شارع المدينة المنورة", "طريق الثمامة",
            "شارع الأمير محمد بن عبدالعزيز", "طريق الرياض جدة",
            "شارع صلاح الدين", "طريق القصيم", "شارع الملك سلمان",
            "شارع الأمير تركي الأول", "طريق الشفا", "شارع البنوك",
        ],
        "zip_format": "1####",
        "phone_code": "+966", "currency": "SAR", "continent": "Asia",
    },
    "United Arab Emirates": {
        "cities": [
            "دبي", "أبوظبي", "الشارقة", "العين", "عجمان",
            "رأس الخيمة", "الفجيرة", "أم القيوين", "دبا الفجيرة",
            "خورفكان", "كلباء", "مدينة زايد", "ليوا", "المرفأ",
            "الظفرة", "رويس", "غياثي", "السمحة",
        ],
        "districts": [
            "المرسى (Marina)", "وسط المدينة (Downtown)", "جميرا",
            "الخالدية", "القصباء", "خليفة", "ديرة", "بر دبي",
            "الكرامة", "البرشاء", "مردف", "الروضة", "المصلى",
            "شاطئ الراحة", "الريم", "القرهود", "الوحيدة", "المينا",
            "الزاهية", "النهدة", "الصفا", "الوصل",
        ],
        "streets": [
            "شارع الشيخ زايد", "طريق الكورنيش", "شارع الوحدة",
            "شارع حصة", "شارع المطار", "شارع الخليج",
            "طريق دبي العين", "شارع إم غلينا", "طريق الشيخ محمد بن زايد",
            "شارع الرقة", "طريق الإمارات", "شارع الكورنيش أبوظبي",
            "طريق الشيخ خليفة", "شارع النصر", "شارع البطين",
            "شارع السلامة", "شارع المتنزه", "طريق المطار الدولي دبي",
            "شارع المجاز", "طريق الشارقة دبي",
        ],
        "zip_format": "#####",
        "phone_code": "+971", "currency": "AED", "continent": "Asia",
    },
    "Egypt": {
        "cities": [
            "القاهرة", "الإسكندرية", "الجيزة", "المنصورة", "شرم الشيخ",
            "الأقصر", "أسوان", "طنطا", "الزقازيق", "دمياط", "بورسعيد",
            "الإسماعيلية", "السويس", "المنيا", "أسيوط", "سوهاج",
            "الفيوم", "بنها", "الغردقة", "المحلة الكبرى", "كفر الشيخ",
            "شبين الكوم", "بني سويف", "أبو ظبي الجديدة",
        ],
        "districts": [
            "المعادي", "الزمالك", "مصر الجديدة", "سموحة", "المهندسين",
            "الدقي", "التجمع الخامس", "عين شمس", "السيدة زينب", "حلوان",
            "العجوزة", "الهرم", "مدينة نصر", "الشروق", "أكتوبر",
            "إمبابة", "الماظة", "العباسية", "شبرا", "بولاق",
            "منيل الروضة", "الجيزة الجديدة", "الرحاب",
        ],
        "streets": [
            "شارع التسعين", "كورنيش النيل", "شارع فؤاد",
            "شارع الهرم", "شارع قصر النيل", "شارع رمسيس",
            "شارع السودان", "طريق المعادي", "شارع التحرير",
            "شارع جامعة الدول العربية", "شارع المرج", "طريق الأتوستراد",
            "شارع عباس العقاد", "شارع مصطفى النحاس", "شارع الفلكي",
            "شارع بغداد", "شارع صلاح سالم", "طريق الإسكندرية الصحراوي",
            "شارع البحر الأعظم", "شارع القصر العيني",
        ],
        "zip_format": "#####",
        "phone_code": "+20", "currency": "EGP", "continent": "Africa",
    },
    "Kuwait": {
        "cities": [
            "مدينة الكويت", "السالمية", "حولي", "الفروانية", "الجهراء",
            "الأحمدي", "مبارك الكبير", "صباح السالم", "الفنطاس",
            "الرقة", "بيان", "السلام", "الري", "الصليبيخات",
            "الشامية", "النزهة", "الضجيج", "القرين",
        ],
        "districts": [
            "بيان", "مشرف", "الجابرية", "الرميثية", "المنصورية",
            "الخالدية", "الزهراء", "العديلية", "السرة", "البدع",
            "الروضة", "قرطبة", "حطين", "اليرموك", "الشعب",
            "فهد الأحمد", "سلوى", "ضاحية عبدالله السالم",
        ],
        "streets": [
            "شارع الخليج العربي", "طريق الفحيحيل", "شارع سالم المبارك",
            "طريق الدائري الرابع", "طريق الدائري الخامس", "شارع الملك فهد",
            "شارع الجابرية", "طريق المطار", "شارع فهد السالم",
            "شارع مبارك الكبير", "طريق السبت", "شارع الشهداء",
            "طريق المسيلة", "شارع البحر", "طريق الجهراء",
            "شارع الغزالي", "طريق بنيدر", "شارع الأمير محمد",
        ],
        "zip_format": "#####",
        "phone_code": "+965", "currency": "KWD", "continent": "Asia",
    },
    "Qatar": {
        "cities": [
            "الدوحة", "الريان", "الوكرة", "الخور", "لوسيل",
            "الشمال", "أم صلال", "دخان", "الوكير", "الشيحانية",
            "الكرعانة", "مسيعيد", "الخريطيات", "رأس لفان",
            "المعاميرية", "الثقب", "الروضة", "الضاين",
        ],
        "districts": [
            "اللؤلؤة (The Pearl)", "الدفنة", "مشيرب", "السد", "الوعب",
            "الهلال", "النصر", "فريج عبدالعزيز", "الغانم", "الغرافة",
            "الروضة", "المنيرة", "الخليفات", "أم قرن", "المعمورة",
            "فريج بن عمران", "الميفعة", "الربيعة",
        ],
        "streets": [
            "كورنيش الدوحة", "شارع الوعب", "طريق سلوى",
            "شارع لوسيل الرئيسي", "طريق الدوحة الشمالي",
            "شارع الخليفة", "طريق الجسر", "شارع الغانم",
            "شارع ابن محمود", "طريق المطار", "شارع أبو حمور",
            "طريق اللؤلؤة", "شارع عمر المختار", "طريق الراية",
            "شارع النصر", "طريق صلاح الدين", "شارع السد",
        ],
        "zip_format": "#####",
        "phone_code": "+974", "currency": "QAR", "continent": "Asia",
    },
    "Bahrain": {
        "cities": [
            "المنامة", "المحرق", "الرفاع", "مدينة حمد", "مدينة عيسى",
            "المالكية", "البديع", "سترة", "توبلي", "الزلاق",
            "عالي", "جد علي", "الدور", "الجسرة", "المدينة الشمالية",
            "ميناء سلمان", "البحير", "الحد",
        ],
        "districts": [
            "الجفير", "السيف", "الحورة", "البديع", "العدلية",
            "القضيبية", "سلماباد", "الدوحة", "عراد", "الهملة",
            "أبو صيبع", "بوري", "البسيتين", "السنابس", "الديه",
            "الزنج", "القفول", "المنامة الوسطى",
        ],
        "streets": [
            "شارع الملك فيصل", "طريق الشيخ عيسى", "شارع المعارض",
            "طريق البديع", "طريق الملك حمد", "شارع الخليج",
            "طريق الجسر", "شارع القدس", "طريق الشمال",
            "شارع المنامة", "طريق بوداية", "شارع المطار",
            "طريق عالي", "شارع اليتيم", "شارع الحكومة",
        ],
        "zip_format": "####",
        "phone_code": "+973", "currency": "BHD", "continent": "Asia",
    },
    "Oman": {
        "cities": [
            "مسقط", "صلالة", "صحار", "نزوى", "صور",
            "البريمي", "إبراء", "الرستاق", "خصب", "الخابورة",
            "مدينة النهضة", "بهلاء", "عبري", "ثمريت", "هيماء",
            "منح", "دبا", "الحمراء", "الدقم", "بركاء",
            "السيب", "مطرح", "العامرات",
        ],
        "districts": [
            "القرم", "الخوير", "روي", "المعبيلة", "بوشر",
            "السيب", "الموالح", "المطرح", "الغبرة", "وادي كبير",
            "الخوض", "الأنصب", "الحيل", "العذيبة", "أزيكي",
            "الرسيل", "الطيويين", "السيح",
        ],
        "streets": [
            "شارع السلطان قابوس", "طريق المطار", "شارع المينا",
            "طريق مسقط السريع", "شارع الجامعة", "طريق صلالة المزدوج",
            "شارع العام", "طريق نزوى", "شارع صحار الساحلي",
            "طريق السريع مسقط إبراء", "شارع المعارض", "طريق البريمي",
            "شارع الصداره", "طريق الجبل الأخضر", "شارع الوطني",
        ],
        "zip_format": "###",
        "phone_code": "+968", "currency": "OMR", "continent": "Asia",
    },
    "Jordan": {
        "cities": [
            "عمان", "إربد", "الزرقاء", "العقبة", "مادبا",
            "الكرك", "جرش", "السلط", "معان", "الطفيلة",
            "المفرق", "أجلون", "رمثا", "الرصيفة", "وادي موسى",
            "الهاشمية", "الأزرق", "شرحبيل", "سوف",
        ],
        "districts": [
            "عبدون", "الشميساني", "جبل عمان", "تلاع العلي", "الصويفية",
            "الرابية", "دابوق", "السابع", "الجاردنز", "ماركا",
            "أبو نصير", "قريات", "خريبة السوق", "النزهة", "الحي الشرقي",
            "العبدلي", "الجبيهة", "المدينة الرياضية",
        ],
        "streets": [
            "شارع المدينة المنورة", "شارع مكة", "شارع الجامعة",
            "طريق المطار", "شارع وادي صقرة", "شارع الأميرة هيا",
            "طريق إربد السريع", "شارع الملك الحسين", "شارع السالم",
            "طريق العقبة", "شارع اليرموك", "طريق الأردن",
            "شارع الرينبو", "شارع الثقافة", "طريق الأزرق",
        ],
        "zip_format": "#####",
        "phone_code": "+962", "currency": "JOD", "continent": "Asia",
    },
    "Iraq": {
        "cities": [
            "بغداد", "أربيل", "البصرة", "النجف", "كربلاء",
            "الموصل", "كركوك", "السليمانية", "الحلة", "النجف",
            "الناصرية", "العمارة", "الكوت", "السماوة", "الرمادي",
            "تكريت", "بعقوبة", "الفلوجة", "دهوك", "زاخو",
            "الديوانية", "حلبجة", "الحي",
        ],
        "districts": [
            "المنصور", "الكرادة", "زيونة", "الأعظمية", "الكاظمية",
            "الرشيد", "الدورة", "الجادرية", "العطيفية", "شارع فلسطين",
            "الحارثية", "النهروان", "الزعفرانية", "الشعب",
            "الباب المعظم", "المشتل", "الوزيرية", "القادسية",
        ],
        "streets": [
            "شارع فلسطين", "شارع الرشيد", "طريق المطار",
            "شارع أبو نواس", "شارع الكندي", "طريق بغداد الدولي",
            "شارع المتنبي", "طريق ساحة الفردوس", "شارع الكرادة الخارج",
            "طريق العبيدي", "شارع النضال", "طريق بعقوبة",
            "شارع ابن سينا", "طريق الموصل السريع", "شارع بور سعيد",
        ],
        "zip_format": "#####",
        "phone_code": "+964", "currency": "IQD", "continent": "Asia",
    },
    "Lebanon": {
        "cities": [
            "بيروت", "طرابلس", "صيدا", "جبيل", "جونية",
            "زحلة", "بعلبك", "النبطية", "صور", "بيت الدين",
            "عاليه", "بروماك", "حارة صخر", "الدامور", "أنطلياس",
            "ضبيه", "مزيارة", "الهرمل", "راشيا",
        ],
        "districts": [
            "الحمرا", "الأشرفية", "فردان", "الجميزة", "الروشة",
            "المزرعة", "الرملة البيضاء", "طريق الجديدة", "شياح",
            "الصيفي", "الجسر", "الشياح", "البسطا", "القنطاري",
            "مار مخايل", "الكرنتينا", "مار الياس",
        ],
        "streets": [
            "شارع الحمرا", "طريق الشام", "شارع فردان",
            "كورنيش بيروت", "طريق صيدا", "شارع الكولا",
            "طريق الضاحية", "شارع أيوب ثابت", "طريق الشياح",
            "شارع عبدالعزيز", "طريق طرابلس السريع", "شارع المتحف",
            "طريق نهر الكلب", "شارع الروشة", "شارع الجسر",
        ],
        "zip_format": "#### ####",
        "phone_code": "+961", "currency": "LBP", "continent": "Asia",
    },
    "Morocco": {
        "cities": [
            "الرباط", "الدار البيضاء", "مراكش", "فاس", "طنجة",
            "أكادير", "مكناس", "وجدة", "كازابلانكا", "الجديدة",
            "القنيطرة", "سلا", "تطوان", "الحسيمة", "بني ملال",
            "خريبكة", "ورزازات", "الصخيرات", "الرحامنة",
            "آسفي", "الناضور", "تزنيت", "إنزكان",
        ],
        "districts": [
            "أكدال", "حسان", "المعاريف", "جيليز", "القصبة",
            "مارتيل", "التقدم", "الرياض", "البوحاجب", "سبع شلولات",
            "الأميرات", "المحيط", "المسيرة", "عين الذئاب", "الفداء",
            "العنق", "بوشنتوف", "درب السلطان",
        ],
        "streets": [
            "شارع محمد الخامس", "شارع الحسن الثاني", "طريق المطار",
            "شارع الفداء", "طريق الدار البيضاء الرباط", "شارع مولاي يوسف",
            "طريق أكادير", "شارع الرياض", "طريق فاس",
            "شارع المنصور الذهبي", "شارع أبو عبيدة", "طريق الجديدة",
            "شارع عمر بن الخطاب", "طريق تطوان", "شارع سيدي بليوط",
            "شارع القدس", "طريق مراكش", "شارع موحمدية",
        ],
        "zip_format": "#####",
        "phone_code": "+212", "currency": "MAD", "continent": "Africa",
    },
    "Algeria": {
        "cities": [
            "الجزائر العاصمة", "وهران", "قسنطينة", "عنابة", "باتنة",
            "بجاية", "سطيف", "تلمسان", "بسكرة", "تيزي وزو",
            "المسيلة", "سكيكدة", "الأغواط", "غرداية", "ورقلة",
            "البليدة", "المدية", "جيجل", "الجلفة", "خنشلة",
            "تيارت", "الشلف", "قالمة",
        ],
        "districts": [
            "باب الزوار", "الحراش", "حيدرة", "بئر مراد رايس",
            "بوزريعة", "الأبيار", "الدار البيضاء", "بن عكنون",
            "دالي إبراهيم", "بلوزداد", "القبة", "سيدي امحمد",
            "الرايس حميدو", "المدنية", "حسين داي", "الشراقة",
        ],
        "streets": [
            "شارع ديدوش مراد", "شارع العربي بن مهيدي", "طريق المطار",
            "شارع أول نوفمبر", "طريق الشلف", "شارع بن خلدون",
            "شارع لاروشيل", "طريق باتنة", "شارع المطار عبان رمضان",
            "طريق وهران", "شارع علي بومنجل", "شارع زيغود يوسف",
            "طريق تيبازة", "شارع سيدي يحيى", "طريق قسنطينة",
        ],
        "zip_format": "#####",
        "phone_code": "+213", "currency": "DZD", "continent": "Africa",
    },
    "Tunisia": {
        "cities": [
            "تونس العاصمة", "صفاقس", "سوسة", "قابس", "بنزرت",
            "قفصة", "بجة", "قيروان", "نابل", "منستير",
            "مدنين", "أريانة", "بن عروس", "زغوان", "سيدي بوزيد",
            "سليانة", "جندوبة", "تطاوين", "القصرين", "المنستير",
        ],
        "districts": [
            "المرسى", "قرطاج", "المنزه", "حلق الوادي",
            "العمران", "رادس", "التضامن", "حي التحرير",
            "الكرم", "باردو", "صيادة", "المنيهلة", "المزة",
            "حمام الشط", "حمامات", "نصر الله",
        ],
        "streets": [
            "شارع الحبيب بورقيبة", "شارع الحرية", "طريق المرسى",
            "شارع الجمهورية", "طريق صفاقس", "شارع فرحات حشاد",
            "طريق منزل بورقيبة", "شارع محمد الخامس", "طريق المنستير",
            "شارع بيزرت", "طريق قرطاج", "شارع الأندلس",
            "طريق سوسة", "شارع ابن خلدون", "شارع العروبة",
        ],
        "zip_format": "####",
        "phone_code": "+216", "currency": "TND", "continent": "Africa",
    },
    "United States": {
        "cities": [
            "New York", "Los Angeles", "Chicago", "Houston", "Phoenix",
            "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose",
            "Austin", "Jacksonville", "Fort Worth", "Columbus", "Charlotte",
            "Indianapolis", "San Francisco", "Seattle", "Denver", "Nashville",
            "Oklahoma City", "El Paso", "Washington", "Boston", "Memphis",
            "Louisville", "Portland", "Las Vegas", "Milwaukee", "Albuquerque",
            "Tucson", "Fresno", "Sacramento", "Atlanta", "Miami",
            "Minneapolis", "Raleigh", "Baltimore", "Cleveland",
        ],
        "districts": [
            "Manhattan", "Brooklyn", "Hollywood", "Downtown", "South Beach",
            "Lincoln Park", "French Quarter", "Capitol Hill", "Midtown",
            "Upper East Side", "SoHo", "Tribeca", "Nob Hill", "Mission District",
            "Beverly Hills", "Venice Beach", "Koreatown", "Chinatown",
            "Little Italy", "Hell's Kitchen", "Williamsburg", "Astoria",
        ],
        "streets": [
            "5th Avenue", "Broadway", "Sunset Blvd", "Michigan Ave",
            "Ocean Drive", "Main St", "Park Avenue", "Rodeo Drive",
            "Peachtree St", "Market Street", "State Street", "Penn Avenue",
            "Commonwealth Ave", "Wilshire Blvd", "Figueroa St", "Grand Ave",
            "Lakeshore Dr", "Oak Street", "Maple Avenue", "Elm Street",
            "Jefferson Ave", "Washington Blvd", "Lincoln Ave", "Monroe St",
        ],
        "zip_format": "#####",
        "states": [
            "NY", "CA", "IL", "TX", "FL", "NV", "WA", "AZ", "CO", "GA",
            "PA", "OH", "MI", "NC", "VA", "TN", "MA", "IN", "MO", "MD",
        ],
        "phone_code": "+1", "currency": "USD", "continent": "North America",
    },
    "United Kingdom": {
        "cities": [
            "London", "Manchester", "Birmingham", "Liverpool", "Edinburgh",
            "Glasgow", "Bristol", "Leeds", "Sheffield", "Bradford",
            "Nottingham", "Leicester", "Coventry", "Kingston upon Hull",
            "Stoke-on-Trent", "Southampton", "Newcastle", "Derby",
            "Portsmouth", "Oxford", "Cambridge", "Brighton", "Norwich",
            "Wolverhampton", "Swindon", "Cardiff", "Belfast",
        ],
        "districts": [
            "Westminster", "Chelsea", "Soho", "Kensington", "Camden Town",
            "Greenwich", "Shoreditch", "Notting Hill", "Brixton", "Hackney",
            "Islington", "Fulham", "Putney", "Clapham", "Mayfair",
            "Canary Wharf", "Bermondsey", "Peckham", "Bethnal Green",
            "Whitechapel", "Bow", "Stratford", "Wimbledon",
        ],
        "streets": [
            "Oxford Street", "Regent St", "Piccadilly", "Abbey Road",
            "Victoria St", "Baker Street", "King's Road", "Bond Street",
            "Carnaby Street", "Fleet Street", "Whitehall", "The Strand",
            "Tottenham Court Road", "Marylebone High St", "Portobello Road",
            "Brompton Road", "Queensway", "Old Street", "Brick Lane",
            "Commercial Road", "Mile End Road", "Roman Road",
        ],
        "zip_format": "??# #??",
        "phone_code": "+44", "currency": "GBP", "continent": "Europe",
    },
    "France": {
        "cities": [
            "Paris", "Marseille", "Lyon", "Toulouse", "Nice",
            "Nantes", "Strasbourg", "Montpellier", "Bordeaux", "Lille",
            "Rennes", "Reims", "Le Havre", "Saint-Etienne", "Toulon",
            "Grenoble", "Dijon", "Angers", "Nimes", "Villeurbanne",
            "Saint-Denis", "Aix-en-Provence", "Le Mans", "Clermont-Ferrand",
        ],
        "districts": [
            "Champs-Elysees", "Montmartre", "Le Marais", "Saint-Germain",
            "Belleville", "Bastille", "Oberkampf", "Pigalle", "Batignolles",
            "Passy", "Auteuil", "Nation", "Republique", "Opéra",
            "Halles", "Odeon", "Luxembourg", "Madeleine",
        ],
        "streets": [
            "Avenue des Champs-Elysees", "Rue de Rivoli", "Boulevard Saint-Germain",
            "Rue du Faubourg Saint-Antoine", "Avenue Montaigne", "Rue de la Paix",
            "Boulevard Haussmann", "Rue Oberkampf", "Avenue de l'Opera",
            "Rue Saint-Honore", "Boulevard Raspail", "Rue de Vaugirard",
            "Avenue de la Grande Armee", "Rue de Bretagne", "Avenue Victor Hugo",
            "Rue Mouffetard", "Boulevard de Clichy", "Rue de Turbigo",
            "Avenue Kleber", "Rue Saint-Denis",
        ],
        "zip_format": "#####",
        "phone_code": "+33", "currency": "EUR", "continent": "Europe",
    },
    "Germany": {
        "cities": [
            "Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne",
            "Stuttgart", "Dusseldorf", "Dortmund", "Essen", "Leipzig",
            "Bremen", "Dresden", "Hanover", "Nuremberg", "Duisburg",
            "Bochum", "Wuppertal", "Bielefeld", "Bonn", "Mannheim",
            "Karlsruhe", "Augsburg", "Wiesbaden", "Gelsenkirchen",
        ],
        "districts": [
            "Mitte", "Kreuzberg", "Schwabing", "Altstadt",
            "Prenzlauer Berg", "Friedrichshain", "Neukölln", "Charlottenburg",
            "Wedding", "Tiergarten", "Schoneberg", "Pankow",
            "Spandau", "Reinickendorf", "Tempelhof", "Steglitz",
            "Laim", "Sendling", "Maxvorstadt", "Haidhausen",
        ],
        "streets": [
            "Unter den Linden", "Kurfuerstendamm", "Friedrichstrasse",
            "Alexanderplatz", "Potsdamer Platz", "Oranienburger Str",
            "Schoenhauser Allee", "Karl-Marx-Strasse", "Grunewaldstrasse",
            "Taunusanlage", "Zeil", "Hauptwache", "Hansaallee",
            "Mariahilfstrasse", "Leopoldstrasse", "Ludwigstrasse",
            "Kaufingerstrasse", "Sendlinger Strasse", "Maximilianstrasse",
        ],
        "zip_format": "#####",
        "phone_code": "+49", "currency": "EUR", "continent": "Europe",
    },
    "Turkey": {
        "cities": [
            "Istanbul", "Ankara", "Izmir", "Antalya", "Bursa",
            "Adana", "Gaziantep", "Konya", "Mersin", "Kayseri",
            "Eskisehir", "Denizli", "Diyarbakir", "Samsun", "Trabzon",
            "Malatya", "Erzurum", "Van", "Mardin", "Kahramanmaras",
            "Sakarya", "Tekirdag", "Bodrum", "Cappadocia",
        ],
        "districts": [
            "Besiktas", "Sisli", "Kadikoy", "Cankaya", "Konak",
            "Muratpasa", "Bakirkoy", "Uskudar", "Fatih", "Beyoglu",
            "Bayrampasa", "Eyupsultan", "Kartal", "Maltepe", "Pendik",
            "Atasehir", "Umraniye", "Sultangazi", "Kucukcekmece",
            "Bahcelievler", "Bagcilar", "Esenler",
        ],
        "streets": [
            "Istiklal Caddesi", "Bagdat Caddesi", "Ataturk Bulvari",
            "Cumhuriyet Cad", "Vali Konagi Cad", "Buyukdere Cad",
            "Halaskargazi Cad", "Ortakoy Sahil", "Barbaros Bulvari",
            "Bosphorus Cad", "Kennedy Cad", "Tahtakale Cad",
            "Divanyolu Cad", "Millet Cad", "Ordu Cad",
            "Buyuk Dere Yolu", "E5 Otoyolu", "TEM Otoyolu",
        ],
        "zip_format": "#####",
        "phone_code": "+90", "currency": "TRY", "continent": "Asia",
    },
    "India": {
        "cities": [
            "New Delhi", "Mumbai", "Bangalore", "Chennai", "Kolkata",
            "Hyderabad", "Ahmedabad", "Pune", "Surat", "Jaipur",
            "Lucknow", "Kanpur", "Nagpur", "Visakhapatnam", "Indore",
            "Thane", "Bhopal", "Patna", "Vadodara", "Ludhiana",
            "Agra", "Nashik", "Coimbatore", "Meerut", "Rajkot",
            "Kochi", "Chandigarh", "Guwahati", "Bhubaneswar",
        ],
        "districts": [
            "Connaught Place", "Bandra", "Koramangala", "T. Nagar",
            "Lajpat Nagar", "Saket", "Dwarka", "Rohini", "Malviya Nagar",
            "Powai", "Andheri", "Juhu", "Indiranagar", "Whitefield",
            "Jayanagar", "Adyar", "Velachery", "Anna Nagar",
            "Salt Lake", "Park Street", "Alipore", "Nizam Palace",
        ],
        "streets": [
            "MG Road", "Marine Drive", "Nehru Place", "Park Street",
            "Rajpath", "Chandni Chowk", "Linking Road", "Carter Road",
            "100 Feet Road", "Old Airport Road", "Anna Salai", "Mount Road",
            "Kamarajar Salai", "Netaji Subhas Road", "Strand Road",
            "SP Mukherjee Road", "Lake Road", "Elgin Road",
            "Camac Street", "Hazra Road", "Gariahat Road",
        ],
        "zip_format": "######",
        "phone_code": "+91", "currency": "INR", "continent": "Asia",
    },
    "China": {
        "cities": [
            "Beijing", "Shanghai", "Guangzhou", "Shenzhen", "Chengdu",
            "Wuhan", "Chongqing", "Xi'an", "Hangzhou", "Nanjing",
            "Tianjin", "Dongguan", "Foshan", "Shenyang", "Qingdao",
            "Zhengzhou", "Jinan", "Harbin", "Changsha", "Kunming",
            "Dalian", "Suzhou", "Ningbo", "Xiamen", "Wuxi",
            "Hefei", "Nanchang", "Guiyang", "Taiyuan",
        ],
        "districts": [
            "Chaoyang", "Pudong", "Tianhe", "Nanshan",
            "Haidian", "Xicheng", "Dongcheng", "Shijingshan",
            "Xuhui", "Jing'an", "Changning", "Minhang",
            "Luwan", "Hongkou", "Yangpu", "Baoshan",
            "Yuexiu", "Liwan", "Haizhu", "Baiyun",
        ],
        "streets": [
            "Chang'an Avenue", "Nanjing Road", "Zhongshan Road",
            "Wangfujing Street", "Huaihai Road", "Renmin Road",
            "Jiefang Road", "Tianhe Road", "Shennan Boulevard",
            "Longhua Road", "Fuzhou Road", "Yan'an Road",
            "Beijing Road", "Guangzhou Avenue", "Dongfeng Road",
            "Xinhua Road", "Jianguo Road", "Changan Street",
        ],
        "zip_format": "######",
        "phone_code": "+86", "currency": "CNY", "continent": "Asia",
    },
    "Japan": {
        "cities": [
            "Tokyo", "Osaka", "Kyoto", "Yokohama", "Nagoya",
            "Sapporo", "Fukuoka", "Kobe", "Kawasaki", "Saitama",
            "Hiroshima", "Sendai", "Chiba", "Kitakyushu", "Sakai",
            "Niigata", "Hamamatsu", "Kumamoto", "Sagamihara",
            "Okayama", "Shizuoka", "Matsuyama", "Kagoshima",
            "Naha", "Kanazawa", "Utsunomiya", "Matsumoto",
        ],
        "districts": [
            "Shibuya", "Shinjuku", "Ginza", "Minato",
            "Roppongi", "Harajuku", "Akihabara", "Asakusa",
            "Ikebukuro", "Ueno", "Nakameguro", "Daikanyama",
            "Shimokitazawa", "Koenji", "Kichijoji", "Umeda",
            "Namba", "Shinsaibashi", "Gion", "Arashiyama",
        ],
        "streets": [
            "Meiji-dori", "Omotesando", "Chuo-dori",
            "Yasukuni-dori", "Shinjuku-dori", "Aoyama-dori",
            "Kotto-dori", "Takeshita-dori", "Nishi-shinjuku",
            "Midosuji", "Dotonbori", "Shinsaibashisuji",
            "Shijo-dori", "Kawaramachi-dori", "Nishiki-dori",
            "Sanjo-dori", "Tokaido", "Sakaisuji",
        ],
        "zip_format": "###-####",
        "phone_code": "+81", "currency": "JPY", "continent": "Asia",
    },
    "Brazil": {
        "cities": [
            "Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador",
            "Fortaleza", "Belo Horizonte", "Manaus", "Curitiba",
            "Recife", "Porto Alegre", "Belem", "Goiania",
            "Guarulhos", "Campinas", "Sao Luis", "Maceio",
            "Natal", "Teresina", "Campo Grande", "Joao Pessoa",
            "Florianopolis", "Santos", "Ribeirao Preto", "Uberlandia",
        ],
        "districts": [
            "Copacabana", "Ipanema", "Centro", "Jardins",
            "Leblon", "Barra da Tijuca", "Lapa", "Santa Teresa",
            "Consolacao", "Moema", "Pinheiros", "Vila Madalena",
            "Itaim Bibi", "Paulista", "Liberdade", "Bela Vista",
            "Perdizes", "Vila Olimpia", "Brooklin", "Morumbi",
        ],
        "streets": [
            "Av. Paulista", "Av. Atlantica", "Rua Oscar Freire",
            "Av. Ipiranga", "Rua Augusta", "Av. Reboucas",
            "Rua dos Pinheiros", "Av. Brigadeiro Faria Lima",
            "Rua Haddock Lobo", "Av. Presidente Vargas",
            "Rua das Laranjeiras", "Rua do Ouvidor",
            "Av. Rio Branco", "Rua Visconde de Piraja",
            "Av. Nossa Senhora de Copacabana", "Rua Barata Ribeiro",
            "Av. Getúlio Vargas", "Rua Voluntários da Pátria",
        ],
        "zip_format": "#####-###",
        "phone_code": "+55", "currency": "BRL", "continent": "South America",
    },
    "Canada": {
        "cities": [
            "Toronto", "Vancouver", "Montreal", "Ottawa", "Calgary",
            "Edmonton", "Winnipeg", "Quebec City", "Hamilton", "Kitchener",
            "Victoria", "Halifax", "Oshawa", "Windsor", "Saskatoon",
            "Regina", "Burnaby", "Richmond", "Laval", "Brampton",
            "Mississauga", "Markham", "Vaughan", "Gatineau", "Surrey",
        ],
        "districts": [
            "Downtown", "Yorkville", "Gastown", "Old Montreal",
            "Kensington Market", "Little Italy", "Greektown", "Chinatown",
            "Distillery District", "Liberty Village", "Leslieville",
            "Little Portugal", "Annex", "Rosedale", "Forest Hill",
            "Mount Pleasant", "Commercial Drive", "East Van", "Yaletown",
        ],
        "streets": [
            "Yonge Street", "Robson Street", "Rue Sainte-Catherine",
            "Bloor Street", "Dundas Street", "King Street West",
            "Queen Street West", "College Street", "Granville Street",
            "Burrard Street", "Hastings Street", "Broadway Ave",
            "Rue Sherbrooke", "Rue Saint-Denis", "Avenue du Parc",
            "Rideau Street", "Sparks Street", "Wellington Street",
        ],
        "zip_format": "?#? #?#",
        "phone_code": "+1", "currency": "CAD", "continent": "North America",
    },
    "Australia": {
        "cities": [
            "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide",
            "Gold Coast", "Canberra", "Newcastle", "Wollongong", "Hobart",
            "Geelong", "Townsville", "Cairns", "Darwin", "Toowoomba",
            "Ballarat", "Bendigo", "Launceston", "Rockingham", "Mackay",
            "Sunshine Coast", "Maitland", "Albury", "Bunbury",
        ],
        "districts": [
            "CBD", "Bondi", "Southbank", "Surfers Paradise",
            "Newtown", "Glebe", "Paddington", "Manly", "Mosman",
            "Richmond", "Fitzroy", "Collingwood", "St Kilda", "Prahran",
            "Fortitude Valley", "New Farm", "Spring Hill", "West End",
            "Fremantle", "Cottesloe", "Glenelg", "North Adelaide",
        ],
        "streets": [
            "George Street", "Collins Street", "Queen Street",
            "Pitt Street", "Elizabeth Street", "William Street",
            "Flinders Street", "Swanston Street", "Bourke Street",
            "Adelaide Street", "Brunswick Street", "Oxford Street",
            "Crown Street", "King Street", "Victoria Street",
            "Murray Street", "Wellington Street", "Hay Street",
            "High Street", "Chapel Street",
        ],
        "zip_format": "####",
        "phone_code": "+61", "currency": "AUD", "continent": "Oceania",
    },
    "Russia": {
        "cities": [
            "Moscow", "Saint Petersburg", "Kazan", "Novosibirsk",
            "Yekaterinburg", "Nizhny Novgorod", "Chelyabinsk", "Samara",
            "Omsk", "Rostov-on-Don", "Ufa", "Krasnoyarsk", "Voronezh",
            "Perm", "Volgograd", "Krasnodar", "Saratov", "Tyumen",
            "Tolyatti", "Izhevsk", "Barnaul", "Ulyanovsk", "Irkutsk",
            "Vladivostok", "Sochi", "Yaroslavl", "Khabarovsk",
        ],
        "districts": [
            "Arbat", "Nevsky", "Kremlin District", "Kitay-Gorod",
            "Tverskoy", "Zamoskvorechye", "Khamovniki", "Presnenskiy",
            "Basmanniy", "Taganskiy", "Yakimanka", "Dorogomilovo",
            "Frunzenskiy", "Vasileostrovskiy", "Petrogradskiy",
            "Kalininsky", "Kirovsky", "Primorsky",
        ],
        "streets": [
            "Tverskaya Street", "Nevsky Prospekt", "Arbat Street",
            "Leninsky Prospekt", "Kutuzovsky Prospekt", "Garden Ring",
            "Novy Arbat", "Sadovaya Street", "Liteynyy Prospekt",
            "Moskovsky Prospekt", "Bolshoy Prospekt", "Vasilievsky Island",
            "Sovetskaya Street", "Karl Marx Street", "Lenin Street",
            "October Revolution Street", "Pushkin Street",
        ],
        "zip_format": "######",
        "phone_code": "+7", "currency": "RUB", "continent": "Europe",
    },
    "South Korea": {
        "cities": [
            "Seoul", "Busan", "Incheon", "Daegu", "Daejeon",
            "Gwangju", "Ulsan", "Suwon", "Seongnam", "Goyang",
            "Bucheon", "Yongin", "Cheongju", "Ansan", "Jeonju",
            "Anyang", "Changwon", "Pohang", "Cheonan", "Hwaseong",
            "Gimhae", "Masan", "Jinju", "Iksan", "Gimpo",
            "Pyeongtaek", "Wonju", "Namyangju", "Gangneung",
            "Jeju", "Mokpo", "Gumi", "Gunsan", "Sokcho",
        ],
        "districts": [
            "Gangnam-gu", "Seocho-gu", "Mapo-gu", "Jongno-gu",
            "Yongsan-gu", "Songpa-gu", "Dongjak-gu", "Gwanak-gu",
            "Seongbuk-gu", "Nowon-gu", "Dobong-gu", "Eunpyeong-gu",
            "Haeundae-gu", "Suyeong-gu", "Buk-gu", "Nam-gu",
            "Jung-gu", "Seo-gu", "Sasang-gu", "Yeonje-gu",
            "Suseong-gu", "Dalseo-gu", "Buk-gu Daegu", "Dong-gu",
        ],
        "streets": [
            "Gangnam-daero", "Teheran-ro", "Sejong-daero",
            "Itaewon-ro", "Hongik-ro", "Euljiro", "Namdaemun-ro",
            "Jongno", "Sinchon-ro", "Apgujeong-ro", "Dosan-daero",
            "Garosugil", "Olympic-daero", "Haeundae-ro", "Nampo-dong",
            "Seomyeon-ro", "Dongseong-ro", "Suseong-ro",
            "Daejeon-daero", "Jungang-no", "Wolpyeong-ro",
            "Chungjangno", "Geumnam-ro", "Jungwon-daero",
        ],
        "zip_format": "#####",
        "phone_code": "+82", "currency": "KRW", "continent": "Asia",
    },
    "Mexico": {
        "cities": [
            "Mexico City", "Guadalajara", "Monterrey", "Cancun",
            "Puebla", "Tijuana", "Leon", "Juarez", "Merida",
            "Chihuahua", "Zapopan", "San Luis Potosi", "Aguascalientes",
            "Queretaro", "Morelia", "Hermosillo", "Mexicali", "Culiacan",
            "Acapulco", "Torreon", "Saltillo", "Tlajomulco", "Veracruz",
            "San Luis Rio Colorado", "Villahermosa",
        ],
        "districts": [
            "Polanco", "Condesa", "Roma Norte", "Centro Historico",
            "Reforma", "Pedregal", "Coyoacan", "Xochimilco",
            "Del Valle", "Satelite", "Narvarte", "Naucalpan",
            "Lomas de Chapultepec", "Santa Fe", "Interlomas",
            "Observatorio", "Lindavista", "Tepito", "Tlatelolco",
        ],
        "streets": [
            "Av. Reforma", "Av. Insurgentes", "Av. Chapultepec",
            "Av. Universidad", "Paseo de la Reforma", "Circuito Interior",
            "Av. Constituyentes", "Blvd. Adolfo Lopez Mateos",
            "Av. Ejercito Nacional", "Av. Viaducto Miguel Aleman",
            "Calzada de Tlalpan", "Av. Taxquena", "Periférico Sur",
            "Av. Revolucion", "Av. Hidalgo", "Av. Juarez",
        ],
        "zip_format": "#####",
        "phone_code": "+52", "currency": "MXN", "continent": "North America",
    },
    "Spain": {
        "cities": [
            "Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza",
            "Malaga", "Murcia", "Palma", "Las Palmas", "Bilbao",
            "Alicante", "Cordoba", "Valladolid", "Vigo", "Gijon",
            "Hospitalet", "Vitoria-Gasteiz", "Santa Cruz", "Granada",
            "Oviedo", "Badalona", "Cartagena", "Terrassa", "Sabadell",
        ],
        "districts": [
            "Salamanca", "Eixample", "El Born", "Triana",
            "Barrio de las Letras", "Malasana", "Chueca", "La Latina",
            "Lavapies", "Retiro", "Sol", "Gran Via",
            "Gracia", "Poble Sec", "El Raval", "Barceloneta",
            "Poblenou", "Sarria", "Sant Gervasi", "Nerja",
        ],
        "streets": [
            "Gran Via", "La Rambla", "Paseo de la Castellana",
            "Calle Serrano", "Paseo del Prado", "Calle Fuencarral",
            "Calle Mayor", "Calle Arenal", "Paseo de Gracia",
            "Calle Alcala", "Via Laietana", "Calle Urgell",
            "Avenida Diagonal", "Calle Muntaner", "Rambla Catalunya",
            "Calle Bruc", "Calle Valencia", "Calle Aragon",
        ],
        "zip_format": "#####",
        "phone_code": "+34", "currency": "EUR", "continent": "Europe",
    },
    "Italy": {
        "cities": [
            "Rome", "Milan", "Florence", "Naples", "Venice",
            "Turin", "Bologna", "Genoa", "Palermo", "Catania",
            "Bari", "Verona", "Messina", "Padua", "Trieste",
            "Brescia", "Taranto", "Prato", "Modena", "Reggio Calabria",
            "Livorno", "Cagliari", "Perugia", "Ravenna", "Rimini",
        ],
        "districts": [
            "Trastevere", "Brera", "San Marco", "Centro Storico",
            "Prati", "Testaccio", "Monti", "Ostiense",
            "Navigli", "Isola", "Porta Romana", "Porta Ticinese",
            "Dorsoduro", "Cannaregio", "Castello", "Santa Croce",
            "Oltrarno", "Santa Maria Novella", "San Lorenzo",
        ],
        "streets": [
            "Via del Corso", "Via Montenapoleone", "Via Roma",
            "Via Nazionale", "Via Veneto", "Via Condotti",
            "Via Cola di Rienzo", "Via del Tritone", "Via Appia Antica",
            "Corso Buenos Aires", "Via Torino", "Via Dante",
            "Corso Vittorio Emanuele", "Via Manzoni", "Via Moscova",
            "Via della Spiga", "Corso Venezia", "Via Maggio",
        ],
        "zip_format": "#####",
        "phone_code": "+39", "currency": "EUR", "continent": "Europe",
    },

    # ── Europe (new) ──────────────────────────────────────────────────────────

    "Netherlands": {
        "cities": [
            "Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven",
            "Groningen", "Tilburg", "Almere", "Breda", "Nijmegen",
            "Apeldoorn", "Haarlem", "Arnhem", "Zaanstad", "Amersfoort",
            "Haarlemmermeer", "Enschede", "Zwolle", "Maastricht", "Leiden",
        ],
        "districts": [
            "Jordaan", "De Pijp", "Oud-Zuid", "Centrum", "Noord",
            "Oost", "West", "Buitenveldert", "Watergraafsmeer",
            "Coolsingel", "Kop van Zuid", "Hillegersberg",
            "Statenkwartier", "Laak", "Centrum Utrecht", "Oud-West",
        ],
        "streets": [
            "Kalverstraat", "Damrak", "Herengracht", "Keizersgracht",
            "Prinsengracht", "Nieuwendijk", "Leidsestraat", "Rokin",
            "Coolsingel", "Blaak", "Lijnbaan", "Spuistraat",
            "Vredenburg", "Lange Viestraat", "Oudegracht",
        ],
        "zip_format": "#### ??",
        "phone_code": "+31", "currency": "EUR", "continent": "Europe",
    },
    "Sweden": {
        "cities": [
            "Stockholm", "Gothenburg", "Malmö", "Uppsala", "Västerås",
            "Örebro", "Linköping", "Helsingborg", "Jönköping", "Norrköping",
            "Lund", "Umeå", "Gävle", "Borås", "Södertälje",
            "Eskilstuna", "Halmstad", "Växjö", "Karlstad", "Sundsvall",
        ],
        "districts": [
            "Södermalm", "Östermalm", "Kungsholmen", "Vasastan", "Gamla Stan",
            "Hisingen", "Majorna", "Linnéstaden", "Avenyn", "Mölndal",
            "Husie", "Limhamn", "Huskvarna", "Råslätt",
        ],
        "streets": [
            "Drottninggatan", "Strandvägen", "Kungsgatan", "Götgatan",
            "Sveavägen", "Avenyn", "Linnégatan", "Hamngatan",
            "Karlavägen", "Birger Jarlsgatan", "Norrmalmstorg",
            "Fredsgatan", "Östra Hamngatan", "Kungsportsavenyn",
        ],
        "zip_format": "### ##",
        "phone_code": "+46", "currency": "SEK", "continent": "Europe",
    },
    "Norway": {
        "cities": [
            "Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen",
            "Fredrikstad", "Kristiansand", "Sandnes", "Tromsø", "Sarpsborg",
            "Skien", "Ålesund", "Sandefjord", "Haugesund", "Tønsberg",
            "Moss", "Porsgrunn", "Bodø", "Arendal", "Hamar",
        ],
        "districts": [
            "Frogner", "Grünerløkka", "Majorstuen", "Bryggen", "Nordnes",
            "Bergenhus", "Midtbyen", "Bakklandet", "Ilsvika", "Stavanger Sentrum",
            "Hillevåg", "Hundvåg", "Sentrum Oslo", "Alna",
        ],
        "streets": [
            "Karl Johans gate", "Storgata", "Bogstadveien", "Bryggen",
            "Torggata", "Møllendalsveien", "Stranden", "Øvre Holmegate",
            "Nedre Strandgate", "Kirkegata", "Søndre gate", "Kongens gate",
        ],
        "zip_format": "####",
        "phone_code": "+47", "currency": "NOK", "continent": "Europe",
    },
    "Switzerland": {
        "cities": [
            "Zurich", "Geneva", "Basel", "Bern", "Lausanne",
            "Lucerne", "St. Gallen", "Lugano", "Winterthur", "Biel",
            "Thun", "Köniz", "La Chaux-de-Fonds", "Schaffhausen", "Fribourg",
            "Chur", "Vernier", "Neuchâtel", "Uster", "Sion",
        ],
        "districts": [
            "Kreis 1", "Langstrasse", "Enge", "Wiedikon", "Aussersihl",
            "Eaux-Vives", "Jonction", "Plainpalais", "Carouge", "Pâquis",
            "Grossbasel", "Kleinbasel", "Spalen", "Gundeldingen", "Matte",
        ],
        "streets": [
            "Bahnhofstrasse", "Rue du Rhône", "Zähringerstrasse", "Marktgasse",
            "Rennweg", "Limmatquai", "Löwenstrasse", "Augustinergasse",
            "Rue de Rive", "Rue de la Corraterie", "Grand-Rue",
            "Freiestrasse", "Militärstrasse", "Langgasse",
        ],
        "zip_format": "####",
        "phone_code": "+41", "currency": "CHF", "continent": "Europe",
    },
    "Poland": {
        "cities": [
            "Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan",
            "Gdansk", "Szczecin", "Bydgoszcz", "Lublin", "Katowice",
            "Bialystok", "Gdynia", "Czestochowa", "Radom", "Sosnowiec",
            "Torun", "Kielce", "Rzeszow", "Gliwice", "Zabrze",
        ],
        "districts": [
            "Srodmiescie", "Praga", "Mokotow", "Wola", "Kazimierz",
            "Podgorze", "Sroka", "Jeżyce", "Lazarz", "Dębniki",
            "Dolny Sopot", "Wrzeszcz", "Oliwa", "Zaspa", "Chelm",
        ],
        "streets": [
            "Nowy Swiat", "Marszalkowska", "Krakowskie Przedmiescie",
            "Florianska", "Piotrkowska", "Dluga", "Dlug Targ",
            "Ulica Grodzka", "Swietego Jana", "Pl. Rynek Glowny",
            "Aleje Jerozolimskie", "Pulawska", "Aleje Ujazdowskie",
        ],
        "zip_format": "##-###",
        "phone_code": "+48", "currency": "PLN", "continent": "Europe",
    },
    "Portugal": {
        "cities": [
            "Lisbon", "Porto", "Braga", "Coimbra", "Aveiro",
            "Guimaraes", "Evora", "Funchal", "Viana do Castelo", "Setubal",
            "Amadora", "Loures", "Almada", "Seixal", "Sintra",
            "Vila Nova de Gaia", "Gondomar", "Matosinhos", "Cascais", "Oeiras",
        ],
        "districts": [
            "Alfama", "Bairro Alto", "Baixa", "Mouraria", "Chiado",
            "Ribeira", "Bonfim", "Cedofeita", "Arroios", "Estrela",
            "Campolide", "Belem", "Parque das Nacoes", "Lapa",
        ],
        "streets": [
            "Rua Augusta", "Avenida da Liberdade", "Rua do Ouro",
            "Rua das Flores", "Av. dos Aliados", "Rua de Santa Catarina",
            "Rua Garrett", "Largo do Chiado", "Rua do Carmo",
            "Avenida de Roma", "Rua Rodrigues Sampaio",
        ],
        "zip_format": "####-###",
        "phone_code": "+351", "currency": "EUR", "continent": "Europe",
    },
    "Greece": {
        "cities": [
            "Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa",
            "Volos", "Rhodes", "Ioannina", "Kavala", "Chania",
            "Chalcis", "Agrinio", "Katerini", "Serres", "Lamia",
            "Xanthi", "Piraeus", "Peristeri", "Kallithea", "Nikaia",
        ],
        "districts": [
            "Syntagma", "Monastiraki", "Plaka", "Kolonaki", "Exarcheia",
            "Ladadika", "Ano Poli", "Kalamaria", "Triandria",
            "Ampelokipoi", "Zografou", "Galatsi", "Ilion",
        ],
        "streets": [
            "Ermou", "Stadiou", "Kifissias", "Voukourestiou",
            "Tsimiski", "Egnatia", "Aristotelous", "Mitropoleos",
            "Venizelos", "Ag. Dimitriou", "Leoforos Alexandras",
            "Leoforos Vas. Sofias", "Pireos", "Acharnon",
        ],
        "zip_format": "### ##",
        "phone_code": "+30", "currency": "EUR", "continent": "Europe",
    },
    "Belgium": {
        "cities": [
            "Brussels", "Antwerp", "Ghent", "Bruges", "Liege",
            "Namur", "Leuven", "Charleroi", "Mechelen", "Aalst",
            "La Louviere", "Kortrijk", "Hasselt", "Sint-Niklaas", "Mons",
            "Genk", "Ostend", "Roeselare", "Tournai", "Verviers",
        ],
        "districts": [
            "Ixelles", "Schaerbeek", "Molenbeek", "Uccle", "Borgerhout",
            "Berchem", "Patershol", "Dampoort", "Seef", "Het Eilandje",
            "Laeken", "Anderlecht", "Etterbeek", "Woluwe-Saint-Lambert",
        ],
        "streets": [
            "Rue Neuve", "Avenue Louise", "Meir", "Veldstraat",
            "Sint-Pietersnieuwstraat", "Place Royale", "Rue de la Loi",
            "Boulevard Anspach", "Rue du Midi", "Chaussee de Waterloo",
            "Rue Sainte-Catherine", "Place de Brouckere",
        ],
        "zip_format": "####",
        "phone_code": "+32", "currency": "EUR", "continent": "Europe",
    },

    # ── Asia (new) ────────────────────────────────────────────────────────────

    "Indonesia": {
        "cities": [
            "Jakarta", "Surabaya", "Bandung", "Medan", "Bekasi",
            "Tangerang", "Makassar", "Semarang", "Depok", "Palembang",
            "South Tangerang", "Batam", "Pekanbaru", "Bandar Lampung", "Bogor",
            "Padang", "Malang", "Denpasar", "Samarinda", "Balikpapan",
        ],
        "districts": [
            "Menteng", "Kemang", "Sudirman", "Kota Tua", "Rungkut",
            "Tegallega", "Dago", "Tampan", "Medan Baru", "Sawah Besar",
            "Tebet", "Pancoran", "Kebayoran Baru", "Senayan", "Tanah Abang",
        ],
        "streets": [
            "Jl. Sudirman", "Jl. Thamrin", "Jl. Gatot Subroto",
            "Jl. HR Rasuna Said", "Jl. Basuki Rahmat", "Jl. Pemuda",
            "Jl. Raya Bogor", "Jl. Gajah Mada", "Jl. Hayam Wuruk",
            "Jl. Diponegoro", "Jl. Ahmad Yani", "Jl. Imam Bonjol",
        ],
        "zip_format": "#####",
        "phone_code": "+62", "currency": "IDR", "continent": "Asia",
    },
    "Pakistan": {
        "cities": [
            "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Islamabad",
            "Multan", "Gujranwala", "Hyderabad", "Peshawar", "Quetta",
            "Sialkot", "Bahawalpur", "Sargodha", "Sukkur", "Larkana",
            "Rahim Yar Khan", "Abbottabad", "Mirpur", "Sheikhupura", "Jhang",
        ],
        "districts": [
            "DHA", "Gulshan", "PECHS", "Model Town", "Gulberg",
            "Johar Town", "F-6", "F-7", "G-10", "Hayatabad",
            "Saddar", "Clifton", "Bath Island", "Defence", "Bahria Town",
        ],
        "streets": [
            "Sharae Faisal", "Mall Road", "Main Boulevard", "Constitution Avenue",
            "Jinnah Avenue", "Shahrah-e-Quaid-e-Azam", "MM Alam Road",
            "Jail Road", "Canal Road", "GT Road", "Bannu Road",
        ],
        "zip_format": "#####",
        "phone_code": "+92", "currency": "PKR", "continent": "Asia",
    },
    "Thailand": {
        "cities": [
            "Bangkok", "Chiang Mai", "Phuket", "Pattaya", "Khon Kaen",
            "Chiang Rai", "Nakhon Ratchasima", "Hat Yai", "Udon Thani",
            "Nakhon Si Thammarat", "Pak Kret", "Rayong", "Chonburi",
            "Nonthaburi", "Pathum Thani", "Samut Prakan", "Ayutthaya",
        ],
        "districts": [
            "Silom", "Sukhumvit", "Siam", "Ratchada", "Nimman",
            "Old City Chiang Mai", "Kathu", "Wichit", "Bang Rak",
            "Sathon", "Phaya Thai", "Din Daeng", "Huai Khwang",
        ],
        "streets": [
            "Silom Road", "Sukhumvit Road", "Ratchadamri Road",
            "Rama IV Road", "Nimman Road", "Tha Phae Road",
            "Charoen Krung Road", "Yaowarat Road", "Ratchaprasong",
            "Phetchaburi Road", "Lat Phrao Road", "Vibhavadi Rangsit",
        ],
        "zip_format": "#####",
        "phone_code": "+66", "currency": "THB", "continent": "Asia",
    },
    "Singapore": {
        "cities": [
            "Singapore", "Jurong East", "Tampines", "Woodlands", "Bedok",
            "Ang Mo Kio", "Toa Payoh", "Bishan", "Clementi", "Punggol",
            "Sengkang", "Hougang", "Yishun", "Buona Vista", "Novena",
        ],
        "districts": [
            "Orchard", "Marina Bay", "Raffles Place", "Tanjong Pagar",
            "Bugis", "Little India", "Chinatown", "Jurong", "Kallang",
            "Pasir Ris", "Serangoon", "Geylang", "Queenstown",
        ],
        "streets": [
            "Orchard Road", "Marina Boulevard", "South Bridge Road",
            "North Bridge Road", "Victoria Street", "Bras Basah Road",
            "Bencoolen Street", "Serangoon Road", "Rochor Road",
            "Jalan Besar", "Bukit Timah Road", "Upper Bukit Timah Road",
        ],
        "zip_format": "######",
        "phone_code": "+65", "currency": "SGD", "continent": "Asia",
    },
    "Malaysia": {
        "cities": [
            "Kuala Lumpur", "Penang", "Johor Bahru", "Kota Kinabalu",
            "Kuching", "Ipoh", "Shah Alam", "Petaling Jaya", "Subang Jaya",
            "Klang", "Ampang Jaya", "Seremban", "Kota Bharu", "Kuala Terengganu",
            "Alor Setar", "Miri", "Sibu", "Sandakan", "Tawau",
        ],
        "districts": [
            "KLCC", "Bukit Bintang", "Chow Kit", "Bangsar", "Georgetown",
            "Komtar", "JB City Centre", "Gurney Drive", "Desa ParkCity",
            "Mont Kiara", "Damansara", "Puchong", "Cheras",
        ],
        "streets": [
            "Jalan Bukit Bintang", "Jalan Ampang", "Jalan Tuanku Abdul Halim",
            "Lebuh Pantai", "Jalan Gombak", "Jalan Ipoh", "Jalan Duta",
            "Jalan Pudu", "Jalan Raja Laut", "Jalan Hang Tuah",
        ],
        "zip_format": "#####",
        "phone_code": "+60", "currency": "MYR", "continent": "Asia",
    },
    "Philippines": {
        "cities": [
            "Manila", "Quezon City", "Davao", "Cebu City", "Zamboanga",
            "Antipolo", "Taguig", "Caloocan", "Pasig", "Valenzuela",
            "Las Pinas", "Paranaque", "Bacoor", "Muntinlupa", "Makati",
            "Dasmariñas", "Cagayan de Oro", "General Santos", "Bacolod",
        ],
        "districts": [
            "BGC", "Makati CBD", "Ortigas", "Binondo", "Malate",
            "IT Park", "Lahug", "Lanang", "Paco", "Ermita",
            "Poblacion", "Cubao", "Eastwood", "Bonifacio Global City",
        ],
        "streets": [
            "EDSA", "Roxas Boulevard", "Ayala Avenue", "Ortigas Avenue",
            "Commonwealth Avenue", "N. Domingo St", "Marcos Highway",
            "Shaw Boulevard", "Quezon Avenue", "Mabini Street",
        ],
        "zip_format": "####",
        "phone_code": "+63", "currency": "PHP", "continent": "Asia",
    },
    "Vietnam": {
        "cities": [
            "Hanoi", "Ho Chi Minh City", "Da Nang", "Nha Trang",
            "Hoi An", "Hai Phong", "Can Tho", "Hue", "Vung Tau",
            "Bien Hoa", "Thu Dau Mot", "Buon Ma Thuot", "Rach Gia",
            "Long Xuyen", "Quy Nhon", "Phan Thiet", "My Tho",
        ],
        "districts": [
            "Ba Dinh", "Hoan Kiem", "Dong Da", "Hai Ba Trung",
            "Quan 1", "Quan 3", "Son Tra", "Ngu Hanh Son",
            "Thanh Khe", "Cam Le", "Binh Thanh", "Tan Binh", "Phu Nhuan",
        ],
        "streets": [
            "Ho Guom", "Nguyen Hue", "Le Loi", "Tran Phu",
            "Nguyen Van Linh", "Bach Dang", "Phan Chu Trinh",
            "Tran Hung Dao", "Dinh Tien Hoang", "Hang Bai",
        ],
        "zip_format": "######",
        "phone_code": "+84", "currency": "VND", "continent": "Asia",
    },

    # ── Africa (new) ──────────────────────────────────────────────────────────

    "Nigeria": {
        "cities": [
            "Lagos", "Abuja", "Kano", "Ibadan", "Port Harcourt",
            "Benin City", "Maiduguri", "Zaria", "Aba", "Jos",
            "Ilorin", "Onitsha", "Warri", "Abeokuta", "Enugu",
            "Owerri", "Kaduna", "Uyo", "Akure", "Yola",
        ],
        "districts": [
            "Victoria Island", "Lekki", "Ikeja", "Garki", "Wuse",
            "Maitama", "Sabon Gari", "Bodija", "Trans-Amadi", "GRA",
            "Asaba", "New Haven", "Independence Layout", "Aba Road",
        ],
        "streets": [
            "Broad Street", "Ahmadu Bello Way", "Herbert Macaulay Way",
            "Adeola Odeku", "Wuse Market Road", "Adetokunbo Ademola",
            "Ozumba Mbadiwe", "Bourdillon Road", "Awolowo Road",
            "Kingsway Road", "Nnamdi Azikiwe Road",
        ],
        "zip_format": "######",
        "phone_code": "+234", "currency": "NGN", "continent": "Africa",
    },
    "South Africa": {
        "cities": [
            "Johannesburg", "Cape Town", "Durban", "Pretoria",
            "Port Elizabeth", "Bloemfontein", "Nelspruit", "East London",
            "Polokwane", "Kimberley", "Pietermaritzburg", "Rustenburg",
            "Witbank", "George", "Richards Bay", "Vanderbijlpark",
        ],
        "districts": [
            "Sandton", "Rosebank", "Waterfront", "De Waterkant",
            "Umhlanga", "Hatfield", "Arcadia", "Melville",
            "Camps Bay", "Green Point", "Sea Point", "Bo-Kaap",
        ],
        "streets": [
            "Nelson Mandela Square", "Long Street", "Adderley Street",
            "Commissioner Street", "Rivonia Road", "Jan Smuts Avenue",
            "William Nicol Drive", "Buitenkant Street", "Bree Street",
            "Loop Street", "Kloof Street", "De Waal Drive",
        ],
        "zip_format": "####",
        "phone_code": "+27", "currency": "ZAR", "continent": "Africa",
    },
    "Kenya": {
        "cities": [
            "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret",
            "Thika", "Malindi", "Kitale", "Garissa", "Kisii",
            "Nyeri", "Meru", "Kericho", "Embu", "Bungoma",
        ],
        "districts": [
            "Westlands", "Karen", "Kilimani", "CBD", "Nyali",
            "Mombasa Old Town", "Milimani", "Annex", "Upper Hill",
            "Lavington", "Kileleshwa", "Lang'ata", "Rongai",
        ],
        "streets": [
            "Uhuru Highway", "Kenyatta Avenue", "Moi Avenue",
            "Haile Selassie Avenue", "Mama Ngina Street", "Tom Mboya Street",
            "Oginga Odinga Road", "Kimathi Street", "Biashara Street",
        ],
        "zip_format": "#####",
        "phone_code": "+254", "currency": "KES", "continent": "Africa",
    },

    # ── Latin America (new) ───────────────────────────────────────────────────

    "Argentina": {
        "cities": [
            "Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata",
            "Mar del Plata", "San Juan", "Tucuman", "Salta", "Resistencia",
            "Neuquen", "Santa Fe", "Corrientes", "San Luis", "Posadas",
            "San Salvador de Jujuy", "Formosa", "San Rafael", "Bahia Blanca",
        ],
        "districts": [
            "Palermo", "San Telmo", "Recoleta", "Belgrano", "Puerto Madero",
            "Barrio Norte", "Nueva Cordoba", "Guemes", "Villa Crespo",
            "Caballito", "Almagro", "Colegiales", "Chacarita",
        ],
        "streets": [
            "Av. Corrientes", "Av. 9 de Julio", "Florida", "Av. Santa Fe",
            "Av. Rivadavia", "Av. Callao", "Av. Libertador", "Av. del Libertador",
            "Av. Cabildo", "Av. Scalabrini Ortiz", "Thames",
        ],
        "zip_format": "#####",
        "phone_code": "+54", "currency": "ARS", "continent": "South America",
    },
    "Colombia": {
        "cities": [
            "Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena",
            "Bucaramanga", "Manizales", "Pereira", "Cucuta", "Ibague",
            "Santa Marta", "Villavicencio", "Pasto", "Monteria", "Armenia",
            "Valledupar", "Neiva", "Sincelejo", "Popayan", "Tunja",
        ],
        "districts": [
            "El Poblado", "Laureles", "Chapinero", "Usaquen", "La Candelaria",
            "El Centro", "Getsemani", "Bocagrande", "Manga", "Pie de la Popa",
            "La Quinta", "El Prado", "Los Alpes",
        ],
        "streets": [
            "Carrera 7", "Av. El Poblado", "Calle 72", "Carrera 15",
            "El Malecon", "Av. El Lago", "Calle 100", "Carrera 11",
            "Transversal 23", "Calle 26", "Av. NQS",
        ],
        "zip_format": "######",
        "phone_code": "+57", "currency": "COP", "continent": "South America",
    },
    "Chile": {
        "cities": [
            "Santiago", "Valparaiso", "Concepcion", "La Serena", "Antofagasta",
            "Temuco", "Rancagua", "Talca", "Arica", "Iquique",
            "Puerto Montt", "Chillan", "Calama", "Osorno", "Copiapo",
        ],
        "districts": [
            "Providencia", "Miraflores", "Nunoa", "Las Condes", "Vina del Mar",
            "Barrio Italia", "San Miguel", "Santiago Centro", "Recoleta",
            "Vitacura", "Lo Barnechea", "Maipu", "La Florida",
        ],
        "streets": [
            "Av. Providencia", "Av. Apoquindo", "Paseo Ahumada",
            "Av. Libertador B. O'Higgins", "Cerro Alegre", "Av. Nueva Providencia",
            "Merced", "Teatinos", "Monjitas", "Huerfanos",
        ],
        "zip_format": "#######",
        "phone_code": "+56", "currency": "CLP", "continent": "South America",
    },
    "Peru": {
        "cities": [
            "Lima", "Arequipa", "Trujillo", "Cusco", "Chiclayo",
            "Iquitos", "Piura", "Huancayo", "Tacna", "Chimbote",
            "Pucallpa", "Juliaca", "Cajamarca", "Ayacucho", "Huanuco",
        ],
        "districts": [
            "Miraflores", "San Isidro", "Barranco", "Lince", "Cayma",
            "Yanahuara", "El Centro Historico", "Surco", "La Molina",
            "Jesus Maria", "San Borja", "Pueblo Libre", "Magdalena",
        ],
        "streets": [
            "Av. Larco", "Malecon de la Reserva", "Jiron de la Union",
            "Av. Arequipa", "Mariscal Benavides", "Av. El Sol",
            "Av. Jose Pardo", "Calle Schell", "Ovalo Gutiérrez",
        ],
        "zip_format": "#####",
        "phone_code": "+51", "currency": "PEN", "continent": "South America",
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
    "nl": "netherlands", "holland": "netherlands",
    "se": "sweden",
    "no": "norway",
    "ch": "switzerland",
    "pl": "poland",
    "pt": "portugal",
    "gr": "greece",
    "be": "belgium",
    "id": "indonesia",
    "pk": "pakistan",
    "th": "thailand",
    "sg": "singapore",
    "my": "malaysia",
    "ph": "philippines",
    "vn": "vietnam",
    "ng": "nigeria",
    "za": "south africa",
    "ke": "kenya",
    "ar": "argentina",
    "co": "colombia",
    "cl": "chile",
    "pe": "peru",
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


_PHONE_FORMATS = {
    "+1":   lambda: f"+1 ({random.randint(200,999)}) {random.randint(200,999)}-{random.randint(1000,9999)}",
    "+44":  lambda: f"+44 7{random.randint(100,999)} {random.randint(100,999)} {random.randint(100,999)}",
    "+966": lambda: f"+966 5{random.randint(0,9)} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+971": lambda: f"+971 5{random.randint(0,9)} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+20":  lambda: f"+20 1{random.choice(['0','1','2','5'])}{random.randint(10000000,99999999)}",
    "+965": lambda: f"+965 {random.choice(['5','6','9'])}{random.randint(1000000,9999999)}",
    "+974": lambda: f"+974 {random.choice(['3','5','6','7'])}{random.randint(100000,999999)}",
    "+973": lambda: f"+973 3{random.randint(1000000,9999999)}",
    "+968": lambda: f"+968 {random.choice(['7','9'])}{random.randint(1000000,9999999)}",
    "+962": lambda: f"+962 7{random.randint(0,9)} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+964": lambda: f"+964 7{random.randint(10,99)} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+961": lambda: f"+961 {random.choice(['3','70','71','76','78','79'])}{random.randint(100000,999999)}",
    "+212": lambda: f"+212 6{random.randint(10000000,99999999)}",
    "+213": lambda: f"+213 {random.choice(['5','6','7'])}{random.randint(10000000,99999999)}",
    "+216": lambda: f"+216 {random.choice(['2','5','9'])}{random.randint(1000000,9999999)}",
    "+33":  lambda: f"+33 6 {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
    "+49":  lambda: f"+49 1{random.randint(50,79)} {random.randint(1000000,9999999)}",
    "+90":  lambda: f"+90 5{random.randint(10,59)} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+91":  lambda: f"+91 {random.choice(['7','8','9'])}{random.randint(100000000,999999999)}",
    "+86":  lambda: f"+86 1{random.randint(30,99)} {random.randint(1000,9999)} {random.randint(1000,9999)}",
    "+81":  lambda: f"+81 {random.choice(['70','80','90'])}-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
    "+55":  lambda: f"+55 {random.randint(11,99)} 9{random.randint(1000,9999)}-{random.randint(1000,9999)}",
    "+61":  lambda: f"+61 4{random.randint(10,99)} {random.randint(100,999)} {random.randint(100,999)}",
    "+7":   lambda: f"+7 9{random.randint(10,99)} {random.randint(100,999)}-{random.randint(10,99)}-{random.randint(10,99)}",
    "+82":  lambda: f"+82-10-{random.randint(1000,9999)}{random.randint(100,9999)}",
    "+52":  lambda: f"+52 1 {random.randint(55,99)}{random.randint(10000000,99999999)}",
    "+34":  lambda: f"+34 6{random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
    "+39":  lambda: f"+39 3{random.randint(20,99)} {random.randint(100,999)} {random.randint(1000,9999)}",
    # New Europe
    "+31":  lambda: f"+31 6 {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)} {random.randint(10,99)}",
    "+46":  lambda: f"+46 7{random.choice(['0','2','3','6','9'])} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
    "+47":  lambda: f"+47 {random.choice(['4','9'])}{random.randint(10000000,99999999)}",
    "+41":  lambda: f"+41 7{random.choice(['5','6','7','8','9'])} {random.randint(100,999)} {random.randint(10,99)} {random.randint(10,99)}",
    "+48":  lambda: f"+48 {random.choice(['5','6','7','8'])}1{random.randint(1000000,9999999)}",
    "+351": lambda: f"+351 9{random.choice(['1','2','3','6'])} {random.randint(100,999)} {random.randint(1000,9999)}",
    "+30":  lambda: f"+30 6{random.choice(['9','8','7'])}{random.randint(10000000,99999999)}",
    "+32":  lambda: f"+32 4{random.choice(['5','6','7','8','9'])}{random.randint(1000000,9999999)}",
    # New Asia
    "+62":  lambda: f"+62 8{random.choice(['1','5','6','7','8','9'])}{random.randint(10000000,99999999)}",
    "+92":  lambda: f"+92 3{random.choice(['0','1','2','3','4','5'])}{random.randint(10000000,99999999)}",
    "+66":  lambda: f"+66 {random.choice(['06','08','09'])}{random.randint(10000000,99999999)}",
    "+65":  lambda: f"+65 {random.choice(['8','9'])}{random.randint(1000000,9999999)}",
    "+60":  lambda: f"+60 1{random.choice(['1','2','3','4','5','6','7','8','9'])}{random.randint(1000000,9999999)}",
    "+63":  lambda: f"+63 9{random.choice(['1','2','3','4','5','6','7','8','9'])}{random.randint(100000000,999999999)}",
    "+84":  lambda: f"+84 {random.choice(['03','07','08','09'])}{random.randint(10000000,99999999)}",
    # New Africa
    "+234": lambda: f"+234 {random.choice(['070','080','090','081','091'])}{random.randint(10000000,99999999)}",
    "+27":  lambda: f"+27 {random.choice(['6','7','8'])}{random.randint(10000000,99999999)}",
    "+254": lambda: f"+254 7{random.choice(['0','1','2','3','4','5','6','7','8','9'])}{random.randint(1000000,9999999)}",
    # New Latin America
    "+54":  lambda: f"+54 9 {random.choice(['11','351','341','261'])}-{random.randint(1000,9999)}-{random.randint(1000,9999)}",
    "+57":  lambda: f"+57 3{random.choice(['0','1','2','3','5'])}{random.randint(10000000,99999999)}",
    "+56":  lambda: f"+56 9 {random.randint(1000,9999)} {random.randint(1000,9999)}",
    "+51":  lambda: f"+51 9{random.randint(10000000,99999999)}",
}


def generate_phone(phone_code):
    if not phone_code:
        phone_code = "+1"
    fmt = _PHONE_FORMATS.get(phone_code)
    if fmt:
        return fmt()
    digits = "".join(str(random.randint(0, 9)) for _ in range(8))
    return f"{phone_code} {digits[:4]}-{digits[4:]}"


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


_SEP  = "\u2501" * 14   # ━━━━━━━━━━━━━━
_FOOT = "\u00a9 DDXSTORE \u2022 @ddx22"

_COUNTRY_CODES = {
    "Algeria": "DZ", "Australia": "AU", "Bahrain": "BH", "Brazil": "BR",
    "Canada": "CA", "China": "CN", "Egypt": "EG", "France": "FR",
    "Germany": "DE", "India": "IN", "Iraq": "IQ", "Italy": "IT",
    "Japan": "JP", "Jordan": "JO", "Kuwait": "KW", "Lebanon": "LB",
    "Mexico": "MX", "Morocco": "MA", "Oman": "OM", "Qatar": "QA",
    "Russia": "RU", "Saudi Arabia": "SA", "South Korea": "KR",
    "Spain": "ES", "Tunisia": "TN", "Turkey": "TR",
    "United Arab Emirates": "AE", "United Kingdom": "GB", "United States": "US",
    # New countries
    "Netherlands": "NL", "Sweden": "SE", "Norway": "NO", "Switzerland": "CH",
    "Poland": "PL", "Portugal": "PT", "Greece": "GR", "Belgium": "BE",
    "Indonesia": "ID", "Pakistan": "PK", "Thailand": "TH", "Singapore": "SG",
    "Malaysia": "MY", "Philippines": "PH", "Vietnam": "VN",
    "Nigeria": "NG", "South Africa": "ZA", "Kenya": "KE",
    "Argentina": "AR", "Colombia": "CO", "Chile": "CL", "Peru": "PE",
}

_GENDERS = ["Male", "Female"]

_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "protonmail.com"]


def _flag(code: str) -> str:
    if not code or len(code) != 2:
        return ""
    return "".join(chr(0x1F1E6 + ord(c) - ord("A")) for c in code.upper())


def _get_flag(country_name: str) -> str:
    code = _COUNTRY_CODES.get(country_name, "")
    return _flag(code)


def _gen_email(full_name: str) -> str:
    parts = full_name.lower().split()
    first = parts[0] if parts else "user"
    last  = parts[-1] if len(parts) > 1 else "user"
    sep   = random.choice([".", "_", ""])
    num   = random.randint(1, 999)
    dom   = random.choice(_DOMAINS)
    return f"{first}{sep}{last}{num}@{dom}"


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
    addr        = get_random_address(country_name, use_arabic)
    phone_code  = CITY_DATA.get(country_name, {}).get("phone_code", "+1")
    phone       = addr.get("phone") or phone_code
    full_name   = addr.get("full_name") or generate_full_name()
    gender      = random.choice(_GENDERS)
    email       = _gen_email(full_name)
    flag        = _get_flag(country_name)
    upper_name  = country_name.upper()

    lines = [
        f"\U0001f4cd {upper_name} \u2014  Address {flag}",
        _SEP,
        f"\U0001f194 Full Name: {full_name}",
        f"\U0001f464 Gender: {gender}",
        f"\U0001f3e0 Street Address: {addr.get('street') or '\u2014'}",
        f"\U0001f3d9\ufe0f City/Town: {addr.get('city') or '\u2014'}",
        f"\U0001f5fa\ufe0f State/Region: {addr.get('state') or '\u2014'}",
        f"\U0001f4ee Postal Code: {addr.get('zip') or '\u2014'}",
        f"\U0001f4de Phone Number: {phone}",
        f"\U0001f4e7 Email: {email}",
        f"\U0001f30d Country: {upper_name} {flag}",
        _SEP,
    ]
    return "\n".join(lines)
