"""
BinUpdateScheduler — Background async scheduler.

Manual-only mode: no automatic runs. Admin triggers via /updatebins.
Provides:
  - run_now()           — fetch all SEED_BINS (new or force-refresh)
  - run_stale_refresh() — refresh only BINs older than N days
  - status()            — live stats for admin panel
"""

import asyncio
import time
from bot.services.bin_updater.updater import BinListUpdater
from bot.utils.logger import get_logger

logger = get_logger("bin_scheduler")

INTERVAL_S      = 24 * 3600
INITIAL_DELAY_S = 0          # no automatic startup run


class BinUpdateScheduler:
    """
    Attach to a running PTB Application and provide on-demand BIN updates.

    Usage (in post_init):
        scheduler = BinUpdateScheduler()
        scheduler.start(application)

    Admin commands call:
        await scheduler.run_now(force=True)
        await scheduler.run_stale_refresh(max_age_days=7)
    """

    def __init__(
        self,
        interval_s:      float = INTERVAL_S,
        initial_delay_s: float = INITIAL_DELAY_S,
    ):
        self.interval_s       = interval_s
        self.initial_delay_s  = initial_delay_s
        self.updater          = BinListUpdater(
            concurrency           = 4,
            delay_between_batches = 1.0,
            max_retries           = 2,
            expand_radius         = 0,
        )
        self._task: asyncio.Task | None = None
        self._last_run: float | None    = None
        self._last_stats: dict | None   = None
        self._running: bool             = False
        self._busy: bool                = False     # True while update is in progress

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def start(self, application=None) -> None:
        """Start the background idle loop (call once from post_init)."""
        if self._running:
            logger.warning("Scheduler already running.")
            return
        self._running = True
        self._task    = asyncio.create_task(self._loop())
        logger.info("BIN scheduler started (manual-only — use /updatebins to trigger)")

    def stop(self) -> None:
        """Cancel the background task gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("BIN scheduler stopped.")
        self._running = False

    # ─── Public update triggers ───────────────────────────────────────────────

    async def run_now(
        self,
        force:       bool = False,
        on_progress=None,
    ) -> dict:
        """
        Trigger a full seed update.

        Args:
            force:       Re-fetch even if BINs already cached.
            on_progress: Optional async/sync callback for live progress.

        Returns:
            Stats dict: fetched / new / updated / failed / duration_s / circuits
        """
        if self._busy:
            return {"error": "update already in progress"}

        self._busy = True
        logger.info(f"Manual BIN update triggered (force={force}).")
        try:
            stats = await self.updater.update_bins(
                force=force, on_progress=on_progress
            )
            self._last_run   = time.time()
            self._last_stats = stats
            return stats
        finally:
            self._busy = False

    async def run_stale_refresh(
        self,
        max_age_days: int  = 7,
        limit:        int  = 200,
        on_progress         = None,
    ) -> dict:
        """
        Refresh only BINs older than max_age_days.
        Lighter than a full update — good for daily maintenance.

        Args:
            max_age_days: Age threshold (default 7 days).
            limit:        Max BINs to refresh per run (default 200).
            on_progress:  Optional progress callback.

        Returns:
            Stats dict.
        """
        if self._busy:
            return {"error": "update already in progress"}

        self._busy = True
        logger.info(f"Stale BIN refresh triggered (max_age={max_age_days}d, limit={limit}).")
        try:
            stats = await self.updater.update_stale_bins(
                max_age_days=max_age_days,
                limit=limit,
                on_progress=on_progress,
            )
            self._last_run   = time.time()
            self._last_stats = stats
            return stats
        finally:
            self._busy = False

    # ─── Status ───────────────────────────────────────────────────────────────

    def status(self) -> dict:
        """Return full scheduler and DB status for admin panel."""
        from bot.database.bin_db import get_bin_db_size, get_full_stats
        from bot.services.bin_updater.sources import get_circuit_status

        next_run_in = None
        if self._last_run is not None:
            elapsed     = time.time() - self._last_run
            next_run_in = max(0, int(self.interval_s - elapsed))

        return {
            "running":      self._running,
            "busy":         self._busy,
            "last_run":     self._last_run,
            "next_run_in":  next_run_in,
            "last_stats":   self._last_stats,
            "total_bins":   get_bin_db_size(),
            "full_stats":   get_full_stats(),
            "circuits":     get_circuit_status(),
        }

    # ─── Internal idle loop ───────────────────────────────────────────────────

    async def _loop(self) -> None:
        """
        Idle loop — no automatic scheduled runs.
        All updates are triggered manually via run_now() or run_stale_refresh().
        """
        try:
            logger.info("BIN scheduler ready (manual-only mode).")
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("BIN scheduler task cancelled.")
