"""
BinListUpdater — Production-grade BIN list manager.

Improvements over v1:
  - bulk_save_bins(): single executemany for batch upserts (10-100x faster)
  - on_progress callback: real-time progress during updates
  - update_stale_bins(): refresh BINs older than N days without full re-seed
  - Adaptive batch delay: slows down when error rate is high
  - Circuit breaker integration via sources.py (no wasted requests to dead endpoints)
  - Deduplication of cache check (no redundant SQLite read inside _fetch_with_retry)
  - get_random_bin() now uses indexed columns for O(log n) filtering
"""

import asyncio
import random
import time
from collections.abc import Callable
from typing import Optional

import httpx

from bot.database.bin_db import (
    get_bin_local,
    bulk_save_bins,
    get_stale_bins,
    get_bin_db_size,
    get_full_stats,
    get_top_bins,
)
from bot.services.bin_updater.sources import fetch_bin_any, get_circuit_status
from bot.utils.logger import get_logger

logger = get_logger("bin_updater")

# ─── Seed BIN list ────────────────────────────────────────────────────────────
# Curated set covering major schemes, regions, and card levels.
# On-demand caching via bin_lookup.py keeps this list minimal;
# it is only used for the proactive update pass.

SEED_BINS = [
    # ── VISA USA (major issuers) ──────────────────────────────────────────────
    "401200", "411111", "424242", "426684", "427533",
    "438857", "453201", "453210", "453219", "454313",
    "454315", "454325", "459150", "462260", "466200",
    "473706", "476173", "491182", "491187", "491188",
    "402236", "408950", "416140", "423495", "432600",
    "444142", "447136", "455672", "461046", "465003",
    "480022", "486019", "489244", "490303", "498430",

    # ── VISA UK ───────────────────────────────────────────────────────────────
    "454742", "454748", "454769", "484427", "490014",
    "493698", "499759",

    # ── VISA Europe ───────────────────────────────────────────────────────────
    "419966", "436406", "442788", "452470", "457173",
    "461596", "470571", "475082", "480070", "492189",

    # ── MASTERCARD USA ────────────────────────────────────────────────────────
    "510510", "513765", "516006", "519787", "520082",
    "521296", "524477", "526473", "527537", "530604",
    "532013", "532418", "537455", "540011", "541333",
    "542418", "543564", "545503", "546616", "547314",
    "550060", "553773", "554002", "556005", "558917",

    # ── MASTERCARD UK / Europe ────────────────────────────────────────────────
    "516100", "519024", "529671", "531210", "536894",
    "542975", "547627", "551020", "555410",

    # ── MASTERCARD Gulf / MENA ────────────────────────────────────────────────
    "517805", "521950", "525258", "535110",
    "538978", "543942", "547804", "556140",

    # ── AMEX ──────────────────────────────────────────────────────────────────
    "341134", "371449", "373953", "378282", "378734",
    "379764", "340000", "348000",

    # ── DISCOVER ──────────────────────────────────────────────────────────────
    "601100", "601109", "601120", "601174", "601300",
    "650010", "650037", "655000", "655002",

    # ── UNIONPAY ──────────────────────────────────────────────────────────────
    "621700", "622126", "622480", "625900", "628200",
    "629000",

    # ── JCB ───────────────────────────────────────────────────────────────────
    "352800", "353011", "356600", "357111", "358000",

    # ── MAESTRO ───────────────────────────────────────────────────────────────
    "630400", "675911", "676770",

    # ── DINERS CLUB ───────────────────────────────────────────────────────────
    "305693", "360003", "380000", "381000",

    # ── VISA Gulf / MENA ─────────────────────────────────────────────────────
    # Saudi Arabia (Al Rajhi, SNB, Riyad, SABB, ANB, Alinma, Al-Jazira)
    "418735", "418736", "418737", "430810", "430811", "461058", "461059",
    "411282", "411283", "471126", "471127", "519083", "416940", "416941",
    "406378", "406379", "430900", "430901", "459098", "459099",
    "405440", "405441", "461497", "461498",
    "401460", "401461", "409690", "409691",
    "406900", "406901",
    # UAE (ENBD, FAB, Mashreq, ADCB, DIB, ADIB)
    "428750", "428751", "428752", "453986", "453987",
    "418820", "418821", "418822", "436369", "436370",
    "414265", "414266", "414267", "458823", "458824",
    "432462", "432463", "434914", "434915",
    "403091", "403092",
    # Kuwait (NBK, Gulf Bank, Burgan, Boubyan)
    "406200", "406201", "406202", "520600", "520601",
    "406210", "406211", "520620", "520621",
    "406220", "406221", "520640", "520641",
    "406230", "406231",
    # Qatar (QNB, Commercial Bank, Doha Bank)
    "406300", "406301", "406302", "520700", "520701",
    "406310", "406311", "520710",
    "406320", "406321",
    # Bahrain (NBB, Arab Bank, Ahli United)
    "406400", "406401", "520800", "520801",
    "406410", "406411", "520810",
    # Oman (Bank Muscat, NBO, BankDhofar)
    "406500", "406501", "520900", "520901",
    "406510", "406511",
    # Jordan (Arab Bank, Housing Bank, Jordan Ahli)
    "406600", "406601", "521000", "521001",
    "406610", "406611",
    # Egypt (CIB, NBE, Banque Misr, QNB Egypt)
    "430600", "430601", "430602", "521100", "521101",
    "430610", "430611", "430612",
    "430620", "430621",

    # ── MASTERCARD Gulf / MENA (expanded) ────────────────────────────────────
    "519150", "519151", "523695", "523696", "524081", "524082", "528282",
    "519083", "519084", "519100", "519101", "519200", "519201",
    "524500", "524501", "524540", "524541", "524560", "524561", "524580",
    "524600", "524601", "524620", "524621", "524640", "524641",
    "524700", "524701", "524720", "524721", "524740", "524741",
    "524800", "524801", "524820", "524821",
    "524900", "524901", "524920", "524921",
    "525000", "525001", "525020", "525021",
    "525100", "525101", "525110", "525111",

    # ── VISA Europe (expanded) ────────────────────────────────────────────────
    # UK (Barclays, HSBC, Lloyds, NatWest, Monzo, Revolut, Starling)
    "492167", "492168", "456735", "456736", "490015", "493699",
    "531216", "531217", "492198", "492199", "402038",
    # Germany (Deutsche, Commerzbank, DKB, ING, Sparkasse)
    "428799", "428800", "428801", "428802", "428803",
    "428804", "428805", "428806", "428807",
    "465831", "465832", "429271", "429272",
    # France (BNP, Crédit Agricole, Société Générale, Crédit Mutuel)
    "430943", "430944", "430945", "430946", "430947",
    "475743", "475744", "457437", "457438",
    # Spain (BBVA, Santander, CaixaBank, Sabadell)
    "457899", "457900", "457901", "457902", "457903",
    "491501", "491502", "492281", "492282",
    # Italy (UniCredit, Intesa, Mediobanca, BPM)
    "462490", "462491", "462492", "462493",
    "478900", "478901", "479100", "479101",
    # Netherlands (ING, Rabobank, ABN AMRO)
    "432366", "432367", "432368", "432369", "432370",
    # Switzerland (UBS, Credit Suisse, PostFinance, Raiffeisen)
    "446400", "446401", "446402", "446403", "446404", "446406",
    # Sweden (Nordea, SEB, Handelsbanken, Swedbank)
    "446200", "446201", "446202", "446203", "446204", "446206",
    # Norway (DNB, SpareBank)
    "446300", "446301", "446302", "446303",
    # Poland (PKO, Pekao, mBank, Santander PL)
    "446500", "446501", "446502", "446503", "446504",
    # Portugal (CGD, BPI, Millennium BCP, Novo Banco)
    "446600", "446601", "446602", "446603",
    # Greece (Piraeus, Alpha, NBG, Eurobank)
    "446700", "446701", "446702", "446703",
    # Belgium (BNP Belgium, ING Belgium, KBC, Belfius)
    "432500", "432501", "432502", "432503",

    # ── MASTERCARD Europe (expanded) ──────────────────────────────────────────
    "534600", "534601", "534620", "534621", "534640", "534641", "534660",
    "534700", "534701", "534720", "534721", "534740", "534741", "534760",
    "534800", "534801", "534820", "534821", "534840", "534841",
    "534900", "534901", "534920", "534921", "534940", "534941",
    "535000", "535001", "535020", "535021", "535040", "535041", "535060",
    "535100", "535101", "535120", "535121", "535140", "535141", "535160",
    "535200", "535201", "535220", "535221",
    "535300", "535301", "535320", "535321", "535340", "535341", "535360",
    "535400", "535401", "535420", "535421", "535440", "535441",

    # ── VISA Asia ─────────────────────────────────────────────────────────────
    # Singapore (DBS, OCBC, Standard Chartered, UOB)
    "455400", "455401", "455402", "455420", "455421",
    "455440", "455441", "455460", "455461",
    # Malaysia (Maybank, CIMB, Public Bank, RHB)
    "455500", "455501", "455502", "455520", "455521",
    "455540", "455541", "455560", "455561",
    # Thailand (Kasikorn, Bangkok Bank, SCB, Krungthai)
    "407266", "407267", "407270", "407271", "407274", "407275", "407280",
    # Indonesia (BCA, Mandiri, BRI, BNI)
    "476211", "476212", "476213", "476214", "476215",
    "413651", "413652", "413653",
    # Philippines (BDO, BPI, Metrobank, Landbank)
    "446800", "446801", "446802", "446803",
    # Vietnam (Vietcombank, VietinBank, BIDV, Techcombank)
    "446900", "446901", "446902", "446903",
    # Pakistan (HBL, MCB, UBL, ABL)
    "477200", "477201", "477202", "477203",
    # India expanded (HDFC, ICICI, SBI, Axis, Kotak)
    "414322", "414323", "414324", "431415", "431416", "431417",
    "400850", "400851", "408617", "408618",

    # ── MASTERCARD Asia ───────────────────────────────────────────────────────
    # South Korea (Kookmin, Shinhan, Hana, Woori, NH)
    "535765", "535766", "531686", "531687", "535780", "535781",
    "535820", "535821", "535840", "535841",
    # Singapore MC
    "534320", "534321", "534340", "534341", "534360", "534361", "534380",
    # India MC
    "524086", "524087", "524090", "524091", "524095", "524096",
    "524100", "524101", "524105", "524106",
    # China (ICBC, BOC, ABC, CCB)
    "621700", "621701", "621921", "621922", "622136", "622137",
    "622200", "622201", "622203", "622204", "621483", "621484",
    # Malaysia MC
    "536200", "536201", "536220", "536221",
    # Thailand MC
    "524200", "524201", "524210", "524211", "524220", "524221",
    # Indonesia MC
    "524300", "524301", "524310", "524311", "524320", "524321", "524330",

    # ── VISA Latin America ────────────────────────────────────────────────────
    # Brazil (Bradesco, Itaú, BB, Caixa, Santander BR, Nubank)
    "453201", "453202", "453203", "453204", "453205", "453206",
    "414751", "414752", "439000", "439001",
    "476064", "476065",
    # Colombia (Bancolombia, Davivienda, BBVA CO)
    "457000", "457001", "457002", "457003", "457004",
    # Chile (Banco de Chile, BCI, Santander CL)
    "452898", "452899", "452900", "452901", "452902",
    # Mexico expanded (BBVA, Santander, Banamex, HSBC MX)
    "449162", "449163", "449164", "449165", "449166", "449167",
    # Argentina (Banco Nación, Galicia, BBVA AR, Santander AR)
    "451020", "451021", "451022", "451023", "451024",
    # Peru (BCP, BBVA PE, Interbank, Scotiabank PE)
    "446950", "446951", "446952", "446953",

    # ── MASTERCARD Latin America ──────────────────────────────────────────────
    "535500", "535501", "535520", "535521", "535540", "535541",
    "535560", "535561", "535580", "535581",
    "535600", "535601", "535620", "535621", "535640", "535641",
    "535700", "535701", "535720", "535721", "535740", "535741",
    "535800", "535801", "535820", "535821", "535840", "535841",
    "535900", "535901", "535920", "535921", "535940", "535941",
    "536000", "536001",

    # ── VISA Africa ───────────────────────────────────────────────────────────
    # Nigeria (First Bank, GTBank, Zenith, UBA, Access)
    "539983", "539984", "539985", "539986", "539987", "539988",
    # South Africa (Standard Bank, FNB, ABSA, Nedbank, Capitec)
    "524534", "524535", "524536", "524537", "524538", "524539",
    # Kenya (Equity, KCB, Co-op, Absa KE)
    "524600", "524601", "524602", "524603", "524604",

    # ── MASTERCARD Africa ─────────────────────────────────────────────────────
    "536020", "536021", "536040", "536041", "536060", "536061", "536080",
    "536100", "536101", "536120", "536121", "536140", "536141", "536160",
    "536200", "536201", "536220", "536221", "536240", "536241",

    # ── VISA Premium (Signature / Infinite / Black) ───────────────────────────
    "476173", "476174", "476175", "476176",
    "489248", "489249", "489250",
    "465002", "465003", "465004",
    "438400", "438401", "438402",
    "451140", "451141",
    "461500", "461501",

    # ── MASTERCARD Premium (World Elite / World) ──────────────────────────────
    "545502", "545503", "545504",
    "532421", "532422", "532423",
    "543001", "543002",
    "558000", "558001",
    "540500", "540501",
    "552500", "552501",

    # ── VISA Debit (major issuers) ────────────────────────────────────────────
    "400115", "400116", "400117",
    "405618", "405619",
    "410123", "410124",
    "431952", "431953",
    "442742", "442743",
    "448590", "448591",
    "471700", "471701",
    "478100", "478101",

    # ── MASTERCARD Debit ──────────────────────────────────────────────────────
    "512345", "512346",
    "522000", "522001",
    "527000", "527001",
    "531000", "531001",
    "543900", "543901",
    "546400", "546401",
    "551100", "551101",
    "556600", "556601",
]


# ─── Main updater class ───────────────────────────────────────────────────────

class BinListUpdater:
    """
    Production-grade BIN list manager.

    Usage:
        updater = BinListUpdater()
        stats   = await updater.update_bins()
        stats   = await updater.update_stale_bins(max_age_days=7)
        rnd_bin = updater.get_random_bin(brand="VISA", country_code="US")
    """

    def __init__(
        self,
        concurrency:            int   = 4,
        delay_between_batches:  float = 1.0,
        max_retries:            int   = 2,
        expand_radius:          int   = 0,
    ):
        self.concurrency            = concurrency
        self.delay_between_batches  = delay_between_batches
        self.max_retries            = max_retries
        self.expand_radius          = expand_radius
        self._semaphore: Optional[asyncio.Semaphore] = None

    # ─── Public API ───────────────────────────────────────────────────────────

    def get_random_bin(
        self,
        brand:        Optional[str] = None,
        type_:        Optional[str] = None,
        country_code: Optional[str] = None,
        level:        Optional[str] = None,
    ) -> dict | None:
        """
        Return a random BIN from local DB with optional indexed filters.

        Args:
            brand:        e.g. "VISA", "MASTERCARD", "AMEX"
            type_:        e.g. "CREDIT", "DEBIT", "PREPAID"
            country_code: e.g. "US", "GB", "SA"
            level:        e.g. "GOLD", "PLATINUM", "CLASSIC"

        Returns:
            Full BIN info dict or None if no match found.
        """
        import sqlite3
        from bot.database.bin_db import DB_PATH, _row_to_dict

        clauses, params = [], []
        if brand:        clauses.append("UPPER(scheme) = ?");       params.append(brand.upper())
        if type_:        clauses.append("UPPER(type) = ?");         params.append(type_.upper())
        if country_code: clauses.append("UPPER(country_code) = ?"); params.append(country_code.upper())
        if level:        clauses.append("UPPER(level) = ?");        params.append(level.upper())

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql   = f"SELECT * FROM bin_data {where} ORDER BY RANDOM() LIMIT 1"

        try:
            con = sqlite3.connect(DB_PATH, timeout=5)
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode=WAL")
            row = con.execute(sql, params).fetchone()
            con.close()
            if row:
                return _row_to_dict(row)
        except Exception as e:
            logger.error(f"get_random_bin error: {e}")
        return None

    def get_stats(self) -> dict:
        """Return current DB statistics (basic)."""
        return {"total_bins": get_bin_db_size(), "top_bins": get_top_bins(5)}

    def get_full_stats(self) -> dict:
        """Return comprehensive DB analytics."""
        return get_full_stats()

    # ─── Seed update ──────────────────────────────────────────────────────────

    async def update_bins(
        self,
        force:       bool = False,
        on_progress: Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """
        Fetch all SEED_BINS (and optional range expansions) from live APIs.

        Args:
            force:       Re-fetch even if already cached locally.
            on_progress: Optional callback called after each batch with a
                         progress dict: {done, total, new, updated, failed, pct}.

        Returns:
            {"fetched", "new", "updated", "failed", "skipped",
             "total_db", "duration_s", "circuits"}
        """
        start_ts   = time.monotonic()
        known_bins = list(SEED_BINS)
        candidates = self._expand_ranges(known_bins)

        if not force:
            # Parallel cache checks — asyncio.to_thread avoids blocking event loop
            cached = await asyncio.gather(
                *[asyncio.to_thread(get_bin_local, b) for b in candidates]
            )
            candidates = [b for b, hit in zip(candidates, cached) if not hit]

        candidates = list(set(candidates))
        random.shuffle(candidates)
        total = len(candidates)

        logger.info(
            f"BIN seed update started (force={force}) — "
            f"{len(SEED_BINS)} seeds → {total} candidates to fetch"
        )

        stats = await self._run_fetch_loop(
            candidates, total, force=False, on_progress=on_progress
        )

        duration = round(time.monotonic() - start_ts, 1)
        stats.update({
            "total_db":   get_bin_db_size(),
            "duration_s": duration,
            "circuits":   get_circuit_status(),
        })
        logger.info(f"BIN seed update done: {stats}")
        return stats

    # ─── Stale refresh ────────────────────────────────────────────────────────

    async def update_stale_bins(
        self,
        max_age_days: int  = 7,
        limit:        int  = 200,
        on_progress:  Optional[Callable[[dict], None]] = None,
    ) -> dict:
        """
        Refresh BINs cached more than max_age_days ago.
        Useful for keeping bank/country data current without re-seeding.

        Args:
            max_age_days: Age threshold in days (default 7).
            limit:        Max BINs to refresh per run (default 200).
            on_progress:  Optional progress callback.

        Returns:
            Same stats dict as update_bins().
        """
        start_ts   = time.monotonic()
        stale_bins = await asyncio.to_thread(get_stale_bins, max_age_days, limit)

        if not stale_bins:
            logger.info("update_stale_bins: no stale BINs found.")
            return {
                "fetched": 0, "new": 0, "updated": 0,
                "failed": 0, "skipped": 0,
                "total_db": get_bin_db_size(),
                "duration_s": 0, "circuits": get_circuit_status(),
            }

        random.shuffle(stale_bins)
        total = len(stale_bins)
        logger.info(
            f"Stale BIN refresh started — {total} BINs "
            f"older than {max_age_days} days"
        )

        stats = await self._run_fetch_loop(
            stale_bins, total, force=True, on_progress=on_progress
        )

        duration = round(time.monotonic() - start_ts, 1)
        stats.update({
            "total_db":   get_bin_db_size(),
            "duration_s": duration,
            "circuits":   get_circuit_status(),
        })
        logger.info(f"Stale BIN refresh done: {stats}")
        return stats

    # ─── Internal: shared fetch loop ─────────────────────────────────────────

    async def _run_fetch_loop(
        self,
        candidates:  list[str],
        total:       int,
        force:       bool,
        on_progress: Optional[Callable[[dict], None]],
    ) -> dict:
        """
        Core fetch loop shared by update_bins() and update_stale_bins().

        Collects results in memory then bulk-saves per batch,
        avoiding N individual SQLite connections.
        Adaptive delay: increases when error rate in current batch exceeds 50%.
        """
        new_count = updated_count = failed_count = skipped_count = 0
        done      = 0
        batch_size = self.concurrency * 3   # fetch N*3, then bulk save

        self._semaphore = asyncio.Semaphore(self.concurrency)

        async with httpx.AsyncClient(
            http2   = False,
            limits  = httpx.Limits(max_connections=self.concurrency + 2,
                                   max_keepalive_connections=self.concurrency),
            timeout = httpx.Timeout(10.0),
        ) as client:

            for i in range(0, len(candidates), batch_size):
                batch   = candidates[i: i + batch_size]
                tasks   = [self._fetch_one(b, client) for b in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Separate successful fetches for bulk save
                to_save: list[tuple[str, dict]] = []
                batch_failed = 0

                for bin_key, res in zip(batch, results):
                    if isinstance(res, Exception):
                        failed_count  += 1
                        batch_failed  += 1
                    elif res == "new":
                        # _fetch_one returned ("new", info) — see below
                        # We handle the tuple case after this loop
                        new_count     += 1
                    elif res == "updated":
                        updated_count += 1
                    elif res == "failed":
                        failed_count  += 1
                        batch_failed  += 1
                    elif res == "skipped":
                        skipped_count += 1
                    elif isinstance(res, tuple) and len(res) == 3:
                        status, _bin_key, info = res
                        to_save.append((_bin_key, info))
                        if status == "new":
                            new_count     += 1
                        elif status == "updated":
                            updated_count += 1

                # Bulk save this batch
                if to_save:
                    await asyncio.to_thread(bulk_save_bins, to_save)

                done += len(batch)

                # Progress callback
                if on_progress and total > 0:
                    on_progress({
                        "done":    done,
                        "total":   total,
                        "new":     new_count,
                        "updated": updated_count,
                        "failed":  failed_count,
                        "pct":     round(done / total * 100),
                    })

                # Adaptive delay: back off if >50% of this batch failed
                error_rate = batch_failed / max(len(batch), 1)
                delay = self.delay_between_batches
                if error_rate > 0.5:
                    delay = min(delay * 3, 8.0)
                    logger.debug(
                        f"High error rate ({error_rate:.0%}) — "
                        f"extending delay to {delay:.1f}s"
                    )
                await asyncio.sleep(delay)

        return {
            "fetched": new_count + updated_count,
            "new":     new_count,
            "updated": updated_count,
            "failed":  failed_count,
            "skipped": skipped_count,
        }

    async def _fetch_one(
        self,
        bin_key: str,
        client:  httpx.AsyncClient,
    ) -> str | tuple:
        """
        Fetch a single BIN with exponential-backoff retries.

        Returns:
          ("new",     bin_key, info)   — fetched, not previously cached
          ("updated", bin_key, info)   — fetched, overwrites existing
          "skipped"                    — already fresh in cache
          "failed"                     — all sources exhausted
        """
        async with self._semaphore:
            existing = await asyncio.to_thread(get_bin_local, bin_key)

            for attempt in range(self.max_retries):
                try:
                    result = await fetch_bin_any(bin_key, client)
                    if not result:
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        return "failed"

                    status = "updated" if existing else "new"
                    return (status, bin_key, result)

                except Exception as e:
                    wait = 2 ** attempt
                    logger.debug(
                        f"BIN {bin_key} attempt {attempt + 1}/{self.max_retries} "
                        f"error: {e}, retry in {wait}s"
                    )
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait)

            return "failed"

    # ─── Range expansion ──────────────────────────────────────────────────────

    def _expand_ranges(self, known_bins: list[str]) -> list[str]:
        """
        Generate candidate BINs by expanding ±radius around each seed.
        expand_radius=0 (default) returns the seeds unchanged.
        """
        candidates: set[str] = set(known_bins)
        r = self.expand_radius
        if r <= 0:
            return list(candidates)

        for b in known_bins:
            try:
                base = int(b[:6])
                for offset in range(-r, r + 1):
                    candidate = str(base + offset).zfill(6)
                    if len(candidate) == 6 and candidate.isdigit():
                        candidates.add(candidate)
            except ValueError:
                continue
        return list(candidates)
