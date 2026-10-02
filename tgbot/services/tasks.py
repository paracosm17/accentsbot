from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)
_background_tasks: set[asyncio.Task[Any]] = set()


def spawn(coro: Coroutine[Any, Any, Any], *, name: str) -> asyncio.Task[Any]:
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_on_done)
    return task


def _on_done(task: asyncio.Task[Any]) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.exception("Background task %s failed", task.get_name(), exc_info=error)


async def drain_background_tasks(timeout: float = 30.0) -> None:
    if not _background_tasks:
        return

    tasks = list(_background_tasks)
    done, pending = await asyncio.wait(tasks, timeout=timeout)

    for task in done:
        _background_tasks.discard(task)

    if pending:
        logger.warning("Cancelling %d background task(s) during shutdown", len(pending))
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
