"""Event-loop lag monitor.

Detects event-loop stalls (blocking sync code, GC pauses, debugger breaks,
process suspension) by comparing the expected wake-up time of a periodic
asyncio task against the actual wake-up time. A single lightweight task is
used — it does no I/O and holds no locks, so it cannot itself cause a stall.
"""

from __future__ import annotations

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


async def monitor_event_loop_lag(
    interval: float = 1.0,
    threshold: float = 2.0,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Log a warning whenever the event loop fails to wake within ``threshold``.

    A large lag means something synchronous ran on the loop. Correlate the
    timestamp with the job that was running to find the culprit.
    """
    loop = asyncio.get_running_loop()
    next_expected = loop.time() + interval
    while stop_event is None or not stop_event.is_set():
        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval)
                return  # stop_event set during the wait
            except TimeoutError:
                pass
        else:
            await asyncio.sleep(interval)

        now = loop.time()
        lag = now - next_expected
        if lag >= threshold:
            logger.warning(
                "Event loop lag detected: lag=%.2fs threshold=%.2fs interval=%.1fs",
                lag,
                threshold,
                interval,
            )
        next_expected = now + interval


async def measure_blocking(fn, *args, **kwargs):
    """Run ``fn`` on a worker thread and return its result.

    Use this ONLY for genuinely CPU-bound, non-async work (e.g. key derivation
    or heavy crypto). Do NOT use it for I/O — the project already has async
    clients for that, and threads would only add contention.
    """
    loop = asyncio.get_running_loop()
    start = time.perf_counter()
    result = await loop.run_in_executor(None, lambda: fn(*args, **kwargs))
    duration = time.perf_counter() - start
    return result, duration
