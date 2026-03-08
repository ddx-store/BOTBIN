"""
DDXSTORE — BIN Database Import Script
Downloads 500K+ BINs from two open-source datasets and merges into local SQLite.
Run once on first deploy:  python scripts/import_bins.py
"""
import httpx, csv, sqlite3, io, sys, os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'bin_cache.db')

SOURCES = [
    {
        'url': 'https://raw.githubusercontent.com/venelinkochev/bin-list-data/master/bin-list-data.csv',
        'name': 'venelinkochev',
        'f_bin': 'BIN', 'f_brand': 'Brand', 'f_type': 'Type',
        'f_level': 'Category', 'f_bank': 'Issuer',
        'f_cc': 'isoCode2', 'f_country': 'CountryName',
    },
    {
        'url': 'https://raw.githubusercontent.com/iannuttall/binlist-data/master/binlist-data.csv',
        'name': 'iannuttall',
        'f_bin': 'bin', 'f_brand': 'brand', 'f_type': 'type',
        'f_level': 'category', 'f_bank': 'issuer',
        'f_cc': 'alpha_2', 'f_country': 'country',
    },
]
BATCH = 2000


def flag(code: str) -> str:
    if not code or len(code) != 2:
        return '\U0001f3f3\ufe0f'
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())


def _upsert_batch(con, batch):
    con.executemany("""
        INSERT INTO bin_data (bin, scheme, type, brand, bank, country, country_code, emoji, level, prepaid)
        VALUES (?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(bin) DO UPDATE SET
            scheme=excluded.scheme, type=excluded.type, brand=excluded.brand,
            bank=excluded.bank, country=excluded.country, country_code=excluded.country_code,
            emoji=excluded.emoji, level=excluded.level
    """, batch)
    con.commit()


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    con = sqlite3.connect(DB_PATH)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA synchronous=NORMAL')
    con.execute("""
        CREATE TABLE IF NOT EXISTS bin_data (
            bin TEXT PRIMARY KEY,
            scheme TEXT, type TEXT, brand TEXT,
            bank TEXT, country TEXT, country_code TEXT,
            emoji TEXT, level TEXT, prepaid INTEGER,
            hit_count INTEGER DEFAULT 0,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    con.execute('CREATE TABLE IF NOT EXISTS bin_stats (bin TEXT PRIMARY KEY, count INTEGER DEFAULT 0)')
    con.execute('CREATE TABLE IF NOT EXISTS request_log (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, detail TEXT, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_country_code ON bin_data(country_code)')
    con.execute('CREATE INDEX IF NOT EXISTS idx_scheme ON bin_data(scheme)')

    grand_total = 0

    for src in SOURCES:
        print(f"\n[{src['name']}] Downloading...")
        try:
            r = httpx.get(src['url'], timeout=120, follow_redirects=True)
            r.raise_for_status()
            print(f"[{src['name']}] Downloaded: {len(r.content):,} bytes")
        except Exception as e:
            print(f"[{src['name']}] FAILED: {e}")
            continue

        reader = csv.DictReader(io.StringIO(r.text))
        batch, total = [], 0

        for row in reader:
            bin_num = (row.get(src['f_bin']) or '').strip()
            if not bin_num or not bin_num.isdigit() or len(bin_num) < 4:
                continue

            brand = (row.get(src['f_brand']) or '').strip().upper()
            type_ = (row.get(src['f_type'])  or '').strip().upper()
            level = (row.get(src['f_level']) or '').strip().upper()
            bank  = (row.get(src['f_bank'])  or '').strip()
            cc    = (row.get(src['f_cc'])    or '').strip().upper()
            ctry  = (row.get(src['f_country']) or '').strip().title()

            batch.append((bin_num, brand, type_, brand, bank, ctry, cc, flag(cc), level, None))
            total += 1

            if len(batch) >= BATCH:
                _upsert_batch(con, batch)
                batch = []
                sys.stdout.write(f'\r  [{src["name"]}] Imported: {total:,}')
                sys.stdout.flush()

        if batch:
            _upsert_batch(con, batch)

        sys.stdout.write(f'\r  [{src["name"]}] Done: {total:,} rows\n')
        grand_total += total

    count = con.execute('SELECT COUNT(*) FROM bin_data').fetchone()[0]
    con.close()
    print(f'\nImport complete!')
    print(f'Total rows processed : {grand_total:,}')
    print(f'Total BINs in DB     : {count:,}')


if __name__ == '__main__':
    main()
