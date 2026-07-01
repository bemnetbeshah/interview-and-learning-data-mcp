"""Small in-memory rate limiter for MCP tool calls."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, DefaultDict


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: int


class InMemoryRateLimiter:
    """Sliding-window limiter keyed by authenticated subject."""

    def __init__(
        self,
        max_requests: int,
        window_seconds: int = 60,
        clock: Callable[[], float] = time.monotonic,
    ):
        if max_requests < 1:
            raise ValueError("max_requests must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.clock = clock
        self._requests: DefaultDict[str, Deque[float]] = defaultdict(deque)

    def check(self, key: str) -> RateLimitResult:
        now = self.clock()
        bucket = self._requests[key]
        cutoff = now - self.window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            retry_after = max(1, int(bucket[0] + self.window_seconds - now))
            return RateLimitResult(False, retry_after)

        bucket.append(now)
        return RateLimitResult(True, 0)
