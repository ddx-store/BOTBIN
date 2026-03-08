import asyncio
from collections import defaultdict
from bot.utils.logger import get_logger

logger = get_logger("queue")

_user_queues: dict = defaultdict(lambda: asyncio.Queue(maxsize=3))
_active_tasks: dict = {}

QUEUE_MAX = 3
LARGE_GEN_THRESHOLD = 50


async def enqueue_task(user_id: int, coro) -> bool:
    queue = _user_queues[user_id]
    if queue.full():
        return False
    await queue.put(coro)
    if not _active_tasks.get(user_id):
        asyncio.create_task(_process_queue(user_id))
    return True


async def _process_queue(user_id: int):
    _active_tasks[user_id] = True
    queue = _user_queues[user_id]
    try:
        while not queue.empty():
            coro = await queue.get()
            try:
                await coro
            except Exception as e:
                logger.error(f"Queue task error for user {user_id}: {e}")
            finally:
                queue.task_done()
    finally:
        _active_tasks[user_id] = False


def get_queue_size(user_id: int) -> int:
    return _user_queues[user_id].qsize()
