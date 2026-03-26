"""
BinUpdateScheduler — Background async scheduler.

Runs update_bins() automatically every 24 hours (or configurable interval).
First run is delayed by INITIAL_DELAY_S to avoid slowing down bot startup.
"""

import asyncio
import time
from bot.services.bin_updater.updater import BinListUpdater
from bot.utils.logger import get_logger

logger = get_logger("bin_scheduler")

INTERVAL_H       = 24
INTERVAL_S       = INTERVAL_H * 3600
INITIAL_DELAY_S  = 0        # no automatic startup run


class BinUpdateScheduler:
    """
    Attach to a running PTB Application and schedule periodic BIN updates.

    Usage (in post_init):
        scheduler = BinUpdateScheduler()
        scheduler.start(application)
    """

    def __init__(
        self,
        interval_s:     float = INTERVAL_S,
        initial_delay_s: float = INITIAL_DELAY_S,
    ):
        self.interval_s      = interval_s
        self.initial_delay_s = initial_delay_s
        self.updater         = BinListUpdater(
            concurrency            = 3,
            delay_between_batches  = 1.2,
            max_retries            = 1,
            expand_radius          = 0,
        )
        self._task: asyncio.Task | None = None
        self._last_run: float | None    = None
        self._last_stats: dict | None   = None
        self._running: bool             = False

    def start(self, application=None) -> None:
        """Start the background update loop (call once, from post_init)."""
        if self._running:
            logger.warning("Scheduler already running.")
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("BIN scheduler started (manual-only — use /updatebins to trigger)")

    def stop(self) -> None:
        """Cancel the background task gracefully."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("BIN scheduler stopped.")
        self._running = False

    async def run_now(self, force: bool = False) -> dict:
        """Trigger an immediate update and return stats (for admin command)."""
        logger.info("Manual BIN update triggered.")
        stats = await self.updater.update_bins(force=force)
        self._last_run   = time.time()
        self._last_stats = stats
        return stats

    def status(self) -> dict:
        """Return current scheduler status dict."""
        from bot.database.bin_db import get_bin_db_size
        next_run_in = None
        if self._last_run is not None:
            elapsed     = time.time() - self._last_run
            next_run_in = max(0, int(self.interval_s - elapsed))

        return {
            "running":      self._running,
            "last_run":     self._last_run,
            "next_run_in":  next_run_in,
            "last_stats":   self._last_stats,
            "total_bins":   get_bin_db_size(),
        }

    # ─── Internal loop ────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        """
        No automatic scheduled runs.
        BINs are cached on-demand via bin_lookup.py.
        Admin can trigger manual update via /updatebins command.
        """
        try:
            logger.info("BIN scheduler ready (manual-only mode).")
            # Idle forever — manual updates are via run_now()
            while True:
                await asyncio.sleep(3600)
        except asyncio.CancelledError:
            logger.info("BIN scheduler task cancelled.")
