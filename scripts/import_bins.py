"""
DDXSTORE — BIN Database Import Script
Downloads 374K+ BINs from open-source dataset and stores them in local SQLite.
Run once on first deploy:  python scripts/import_bins.py
"""
import httpx, csv, sqlite3, io, sys, os

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'bin_cache.db')
CSV_URL = 'https://raw.githubusercontent.com/venelinkochev/bin-list-data/master/bin-list-data.csv'
BATCH   = 2000


def flag(code: str) -> str:
    if not code or len(code) != 2:
        return '\U0001f3f3\ufe0f'
    return ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in code.upper())


def main():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

    print('Downloading BIN database...')
    r = httpx.get(CSV_URL, timeout=120, follow_redirects=True)
    r.raise_for_status()
    print(f'Downloaded: {len(r.content):,} bytes')

    reader = csv.DictReader(io.StringIO(r.text))

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

    batch, total = [], 0

    for row in reader:
        bin_num = row.get('BIN', '').strip()
        if not bin_num or not bin_num.isdigit():
            continue

        brand = (row.get('Brand', '') or '').strip().upper()
        type_ = (row.get('Type', '') or '').strip().upper()
        level = (row.get('Category', '') or '').strip().upper()
        bank  = (row.get('Issuer', '') or '').strip()
        cc    = (row.get('isoCode2', '') or '').strip().upper()
        ctry  = (row.get('CountryName', '') or '').strip().title()

        batch.append((bin_num, brand, type_, brand, bank, ctry, cc, flag(cc), level, None))
        total += 1

        if len(batch) >= BATCH:
            con.executemany("""
                INSERT INTO bin_data (bin, scheme, type, brand, bank, country, country_code, emoji, level, prepaid)
                VALUES (?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(bin) DO UPDATE SET
                    scheme=excluded.scheme, type=excluded.type, brand=excluded.brand,
                    bank=excluded.bank, country=excluded.country, country_code=excluded.country_code,
                    emoji=excluded.emoji, level=excluded.level
            """, batch)
            con.commit()
            batch = []
            sys.stdout.write(f'\r  Imported: {total:,}')
            sys.stdout.flush()

    if batch:
        con.executemany("""
            INSERT INTO bin_data (bin, scheme, type, brand, bank, country, country_code, emoji, level, prepaid)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(bin) DO UPDATE SET
                scheme=excluded.scheme, type=excluded.type, brand=excluded.brand,
                bank=excluded.bank, country=excluded.country, country_code=excluded.country_code,
                emoji=excluded.emoji, level=excluded.level
        """, batch)
        con.commit()

    count = con.execute('SELECT COUNT(*) FROM bin_data').fetchone()[0]
    con.close()
    print(f'\n\nImport complete!')
    print(f'Total BINs in DB: {count:,}')


if __name__ == '__main__':
    main()
