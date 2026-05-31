"""
timeout_utils.py — non-blocking timeout helpers.

ThreadPoolExecutor's context manager waits for running workers on exit. That
defeats API fallbacks when a provider call hangs, so use explicit shutdown.
"""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Callable, TypeVar

T = TypeVar("T")


def run_with_timeout(fn: Callable[[], T], *, timeout_s: float, fallback: T) -> T:
    """Run fn with a hard caller-side timeout and return fallback on timeout/error."""
    executor = ThreadPoolExecutor(max_workers=1)
    future = executor.submit(fn)
    try:
        return future.result(timeout=timeout_s)
    except FutureTimeout:
        future.cancel()
        return fallback
    except Exception:
        return fallback
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


async def run_async_with_timeout(fn: Callable[[], T], *, timeout_s: float, fallback: T) -> T:
    """Async wrapper using a fresh executor so stale default-pool workers cannot block."""
    loop = asyncio.get_running_loop()
    executor = ThreadPoolExecutor(max_workers=1)
    future = loop.run_in_executor(executor, fn)
    try:
        return await asyncio.wait_for(future, timeout=timeout_s)
    except Exception:
        future.cancel()
        return fallback
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
