import unittest

from interview_prep_mcp.rate_limit import InMemoryRateLimiter


class RateLimitTests(unittest.TestCase):
    def test_rate_limiter_blocks_until_window_expires(self):
        now = 1000.0

        def clock():
            return now

        limiter = InMemoryRateLimiter(max_requests=2, window_seconds=60, clock=clock)

        self.assertTrue(limiter.check("user-1").allowed)
        self.assertTrue(limiter.check("user-1").allowed)

        blocked = limiter.check("user-1")
        self.assertFalse(blocked.allowed)
        self.assertGreater(blocked.retry_after_seconds, 0)

        now = 1061.0
        self.assertTrue(limiter.check("user-1").allowed)

    def test_rate_limiter_keys_are_independent(self):
        limiter = InMemoryRateLimiter(max_requests=1, window_seconds=60, clock=lambda: 1000.0)

        self.assertTrue(limiter.check("user-1").allowed)
        self.assertFalse(limiter.check("user-1").allowed)
        self.assertTrue(limiter.check("user-2").allowed)
