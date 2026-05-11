"""Event-driven wait primitives that replace asyncio.sleep polling.

A WaitableSlot is a typed one-shot (re-armable) signal: a consumer awaits
.wait(), and the producer (typically the WS message handler) calls .set(value).

wait_until() exists for cases where the desired state cannot be signaled
from the WS handler. It still uses short polling internally but enforces
a hard timeout.
"""
from __future__ import annotations

import asyncio
from typing import Callable, Generic, TypeVar

T = TypeVar("T")

DEFAULT_TIMEOUT: float = 10.0


class WaitableSlot(Generic[T]):
    """Typed slot a consumer awaits and the producer fills via .set()."""

    __slots__ = ("_value", "_event")

    def __init__(self) -> None:
        self._value: T | None = None
        self._event = asyncio.Event()

    def set(self, value: T) -> None:
        """Store the value and wake any awaiting consumers."""
        self._value = value
        self._event.set()

    def clear(self) -> None:
        """Reset the slot so subsequent waits block again."""
        self._value = None
        self._event.clear()

    def is_set(self) -> bool:
        return self._event.is_set()

    async def wait(self, timeout: float = DEFAULT_TIMEOUT) -> T:
        """Block until set or raise asyncio.TimeoutError on timeout."""
        await asyncio.wait_for(self._event.wait(), timeout=timeout)
        return self._value  # type: ignore[return-value]


async def wait_until(
    predicate: Callable[[], bool],
    *,
    timeout: float = DEFAULT_TIMEOUT,
    poll_interval: float = 0.05,
) -> None:
    """Poll predicate() until truthy or raise asyncio.TimeoutError."""
    async def _loop() -> None:
        while not predicate():
            await asyncio.sleep(poll_interval)

    await asyncio.wait_for(_loop(), timeout=timeout)
