"""
BinListUpdater — Production-grade BIN list manager.

Features:
  - Multi-source fetch with fallback chain
  - BIN range expansion from known seeds
  - Rate-limited async batch fetching
  - Exponential backoff on failures
  - Enriched local SQLite cache
  - Random BIN retrieval with filters
"""

import asyncio
import random
import time
from typing import Optional

import httpx

from bot.database.bin_db import (
    get_bin_local, save_bin_local, get_bin_db_size,
    get_top_bins, track_bin_usage,
)
from bot.services.bin_updater.sources import fetch_bin_any
from bot.utils.logger import get_logger

logger = get_logger("bin_updater")

SEED_BINS = [
    # ── VISA USA (major banks) ──────────────────────────────────
    "401200", "411111", "424242", "426684", "427533",
    "438857", "453201", "453210", "453219", "454313",
    "454315", "454325", "459150", "462260", "466200",
    "473706", "476173", "491182", "491187", "491188",
    "402236", "408950", "416140", "423495", "432600",
    "444142", "447136", "455672", "461046", "465003",
    "480022", "486019", "489244", "490303", "498430",

    # ── VISA UK ─────────────────────────────────────────────────
    "454742", "454748", "454769", "484427", "490014",
    "493698", "499759",

    # ── VISA Europe ─────────────────────────────────────────────
    "419966", "436406", "442788", "452470", "457173",
    "461596", "470571", "475082", "480070", "492189",

    # ── MASTERCARD USA ──────────────────────────────────────────
    "510510", "513765", "516006", "519787", "520082",
    "521296", "524477", "526473", "527537", "530604",
    "532013", "532418", "537455", "540011", "541333",
    "542418", "543564", "545503", "546616", "547314",
    "550060", "553773", "554002", "556005", "558917",

    # ── MASTERCARD UK / Europe ──────────────────────────────────
    "516100", "519024", "529671", "531210", "536894",
    "542975", "547627", "551020", "555410",

    # ── MASTERCARD Gulf / MENA ─────────────────────────────────
    "517805", "521950", "525258", "529671", "535110",
    "538978", "543942", "547804", "556140",

    # ── AMEX ────────────────────────────────────────────────────
    "341134", "371449", "373953", "378282", "378734",
    "379764", "340000", "348000",

    # ── DISCOVER ────────────────────────────────────────────────
    "601100", "601109", "601120", "601174", "601300",
    "650010", "650037", "655000", "655002",

    # ── UNIONPAY ────────────────────────────────────────────────
    "621700", "622126", "622480", "625900", "628200",
    "629000",

    # ── JCB ─────────────────────────────────────────────────────
    "352800", "353011", "356600", "357111", "358000",

    # ── MAESTRO ─────────────────────────────────────────────────
    "630400", "675911", "676770",

    # ── DINERS CLUB ─────────────────────────────────────────────
    "305693", "360003", "380000", "381000",
]


class BinListUpdater:
    """
    Production-grade BIN list manager.

    Usage:
        updater = BinListUpdater()
        stats   = await updater.update_bins()
        rnd_bin = updater.get_random_bin(brand="VISA", country_code="US")
    """

    def __init__(
        self,
        concurrency: int = 3,
        delay_between_batches: float = 1.0,
        max_retries: int = 1,
        expand_radius: int = 0,
    ):
        self.concurrency           = concurrency
        self.delay_between_batches = delay_between_batches
        self.max_retries           = max_retries
        self.expand_radius         = expand_radius
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
        Return a random BIN from local DB with optional filters.

        Args:
            brand:        e.g. "VISA", "MASTERCARD", "AMEX"
            type_:        e.g. "CREDIT", "DEBIT", "PREPAID"
            country_code: e.g. "US", "GB", "SA"
            level:        e.g. "GOLD", "PLATINUM", "CLASSIC"

        Returns:
            Full BIN info dict or None if no match found.
        """
        import sqlite3
        from bot.database.bin_db import DB_PATH

        clauses, params = [], []
        if brand:
            clauses.append("UPPER(scheme) = ?");  params.append(brand.upper())
        if type_:
            clauses.append("UPPER(type) = ?");    params.append(type_.upper())
        if country_code:
            clauses.append("UPPER(country_code) = ?"); params.append(country_code.upper())
        if level:
            clauses.append("UPPER(level) = ?");   params.append(level.upper())

        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        sql   = f"SELECT * FROM bin_data {where} ORDER BY RANDOM() LIMIT 1"

        try:
            con = sqlite3.connect(DB_PATH, timeout=5)
            con.row_factory = sqlite3.Row
            row = con.execute(sql, params).fetchone()
            con.close()
            if row:
                return dict(row)
        except Exception as e:
            logger.error(f"get_random_bin error: {e}")
        return None

    def get_stats(self) -> dict:
        """Return current DB statistics."""
        size     = get_bin_db_size()
        top_bins = get_top_bins(5)
        return {"total_bins": size, "top_bins": top_bins}

    async def update_bins(self, force: bool = False) -> dict:
        """
        Main update routine.

        Steps:
          1. Load current BINs from DB + seed list
          2. Expand ranges around known BINs
          3. Filter to only unknown BINs (unless force=True)
          4. Fetch in rate-limited async batches
          5. Save results, return stats dict

        Args:
            force: Re-fetch even if BIN already cached locally.

        Returns:
            {"fetched": N, "new": N, "updated": N, "failed": N, "duration_s": N}
        """
        start_ts = time.monotonic()
        logger.info(f"BIN update started (force={force})")

        known_bins = self._load_known_bins()
        candidates = self._expand_ranges(known_bins)

        if not force:
            cached_check = await asyncio.gather(
                *[asyncio.to_thread(get_bin_local, b) for b in candidates]
            )
            candidates = [b for b, hit in zip(candidates, cached_check) if not hit]
        candidates = list(set(candidates))
        random.shuffle(candidates)

        logger.info(f"Update plan: {len(known_bins)} known, "
                    f"{len(candidates)} candidates to fetch")

        new_count, updated_count, failed_count = 0, 0, 0
        self._semaphore = asyncio.Semaphore(self.concurrency)

        async with httpx.AsyncClient() as client:
            for i in range(0, len(candidates), self.concurrency * 2):
                batch = candidates[i: i + self.concurrency * 2]
                tasks = [self._fetch_with_retry(b, client, force) for b in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                for res in results:
                    if isinstance(res, Exception):
                        failed_count += 1
                    elif res == "new":
                        new_count += 1
                    elif res == "updated":
                        updated_count += 1
                    elif res == "failed":
                        failed_count += 1

                await asyncio.sleep(self.delay_between_batches)

        duration = round(time.monotonic() - start_ts, 1)
        stats = {
            "fetched":    new_count + updated_count,
            "new":        new_count,
            "updated":    updated_count,
            "failed":     failed_count,
            "total_db":   get_bin_db_size(),
            "duration_s": duration,
        }
        logger.info(f"BIN update done: {stats}")
        return stats

    # ─── Internal helpers ─────────────────────────────────────────────────────

    def _load_known_bins(self) -> list[str]:
        """Return the static seed list only.
        DB bins are not included as candidates — they are already cached
        and we do not want their count to inflate future update cycles.
        """
        return list(SEED_BINS)

    def _expand_ranges(self, known_bins: list[str]) -> list[str]:
        """
        Generate candidate BINs by expanding ±radius around each known BIN.
        Only generates valid 6-digit prefixes.
        """
        candidates: set[str] = set(known_bins)
        r = self.expand_radius
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

    async def _fetch_with_retry(
        self,
        bin_key: str,
        client:  httpx.AsyncClient,
        force:   bool,
    ) -> str:
        """
        Fetch a single BIN with exponential backoff.
        Returns "new" | "updated" | "failed".
        """
        async with self._semaphore:
            for attempt in range(self.max_retries):
                try:
                    existing = await asyncio.to_thread(get_bin_local, bin_key)
                    if existing and not force:
                        return "skipped"

                    result = await fetch_bin_any(bin_key, client)
                    if not result:
                        return "failed"

                    await asyncio.to_thread(save_bin_local, bin_key, result)
                    return "updated" if existing else "new"

                except Exception as e:
                    wait = 2 ** attempt
                    logger.debug(f"BIN {bin_key} attempt {attempt+1} failed: {e}, retry in {wait}s")
                    if attempt < self.max_retries - 1:
                        await asyncio.sleep(wait)

            return "failed"
