
import asyncio
import math
import time
import unittest

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

# Change "politeness" if your module has a different filename.
from crawler.policy_and_politeness.politeness import (
    MAX_BACKOFF_SECONDS,
    PolitenessManager,
    get_host_key,
    parse_retry_after,
)


URL = "https://docs.python.org/3/tutorial/"
OTHER_URL = "https://developer.mozilla.org/en-US/"


# ==========================================================
# 1. HOST KEY TESTS
# ==========================================================

class TestHostKey(unittest.TestCase):

    def test_extract_hostname(self):
        self.assertEqual(
            get_host_key(URL),
            "docs.python.org",
        )

    def test_same_host_different_paths(self):
        urls = [
            "https://docs.python.org/3/tutorial/",
            "https://docs.python.org/3/library/",
            "https://docs.python.org/3/reference/",
        ]

        hosts = {get_host_key(url) for url in urls}

        self.assertEqual(hosts, {"docs.python.org"})

    def test_scheme_and_port_share_host(self):
        self.assertEqual(
            get_host_key("http://docs.python.org:8080/a"),
            get_host_key("https://docs.python.org/b"),
        )

    def test_invalid_urls(self):
        invalid_urls = [
            "not-a-url",
            "/relative/path",
            "ftp://example.com/file",
        ]

        for url in invalid_urls:
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    get_host_key(url)

    def test_invalid_type(self):
        with self.assertRaises(TypeError):
            get_host_key(None)


# ==========================================================
# 2. RETRY-AFTER HEADER TESTS
# ==========================================================

class TestRetryAfter(unittest.TestCase):

    def test_seconds(self):
        self.assertEqual(parse_retry_after("30"), 30.0)

    def test_whitespace(self):
        self.assertEqual(parse_retry_after("  60  "), 60.0)

    def test_zero(self):
        self.assertEqual(parse_retry_after("0"), 0.0)

    def test_missing_header(self):
        self.assertIsNone(parse_retry_after(None))

    def test_invalid_header(self):
        self.assertIsNone(
            parse_retry_after("not-a-valid-date")
        )

    def test_future_http_date(self):
        future = datetime.now(timezone.utc) + timedelta(
            seconds=120
        )

        header = format_datetime(future, usegmt=True)
        result = parse_retry_after(header)

        self.assertIsNotNone(result)
        self.assertGreater(result, 118)
        self.assertLessEqual(result, 120)

    def test_past_http_date(self):
        past = datetime.now(timezone.utc) - timedelta(
            minutes=10
        )

        header = format_datetime(past, usegmt=True)

        self.assertEqual(parse_retry_after(header), 0.0)

    def test_huge_numeric_header(self):
        result = parse_retry_after("9" * 400)

        self.assertEqual(
            result,
            float(MAX_BACKOFF_SECONDS),
        )


# ==========================================================
# 3. CONFIGURATION TESTS
# ==========================================================

class TestConfiguration(unittest.TestCase):

    def test_default_configuration(self):
        manager = PolitenessManager()

        self.assertEqual(
            manager.max_concurrent_per_host, 2
        )
        self.assertEqual(
            manager.min_interval_seconds, 2.0
        )
        self.assertEqual(
            manager.default_backoff_seconds, 60.0
        )

    def test_custom_configuration(self):
        manager = PolitenessManager(
            max_concurrent_per_host=5,
            min_interval_seconds=0.5,
            default_backoff_seconds=10,
            max_backoff_seconds=100,
        )

        self.assertEqual(manager.max_concurrent_per_host, 5)
        self.assertEqual(manager.min_interval_seconds, 0.5)
        self.assertEqual(manager.default_backoff_seconds, 10)
        self.assertEqual(manager.max_backoff_seconds, 100)

    def test_invalid_configuration(self):
        cases = [
            {"max_concurrent_per_host": 0},
            {"max_concurrent_per_host": -1},
            {"max_concurrent_per_host": True},
            {"max_concurrent_per_host": 1.5},
            {"min_interval_seconds": -1},
            {"min_interval_seconds": math.nan},
            {"default_backoff_seconds": math.inf},
            {"max_backoff_seconds": 0},
            {"max_backoff_seconds": -1},
        ]

        for kwargs in cases:
            with self.subTest(config=kwargs):
                with self.assertRaises(ValueError):
                    PolitenessManager(**kwargs)


# ==========================================================
# 4. ASYNC POLITENESS MANAGER TESTS
# ==========================================================

class TestPolitenessManager(
    unittest.IsolatedAsyncioTestCase
):

    async def asyncSetUp(self):
        # Small intervals keep automated tests fast.
        self.manager = PolitenessManager(
            max_concurrent_per_host=2,
            min_interval_seconds=0.05,
            default_backoff_seconds=0.05,
            max_backoff_seconds=0.15,
        )

    # ------------------------------------------------------
    # HOST STATE
    # ------------------------------------------------------

    async def test_host_state_created(self):
        host = await self.manager.acquire(URL)

        self.assertIn(host, self.manager._states)

        self.manager.release(host)

    async def test_host_state_reused(self):
        host = get_host_key(URL)

        state1 = self.manager._get_host_state(host)
        state2 = self.manager._get_host_state(host)

        self.assertIs(state1, state2)

    async def test_different_hosts_have_separate_states(self):
        host1 = get_host_key(URL)
        host2 = get_host_key(OTHER_URL)

        state1 = self.manager._get_host_state(host1)
        state2 = self.manager._get_host_state(host2)

        self.assertIsNot(state1, state2)

    # ------------------------------------------------------
    # SEMAPHORE / CONCURRENCY
    # ------------------------------------------------------

    async def test_two_requests_allowed(self):
        manager = PolitenessManager(
            max_concurrent_per_host=2,
            min_interval_seconds=0,
        )

        host1 = await manager.acquire(URL)
        host2 = await manager.acquire(URL)

        self.assertEqual(host1, host2)

        manager.release(host1)
        manager.release(host2)

    async def test_third_request_must_wait(self):
        manager = PolitenessManager(
            max_concurrent_per_host=2,
            min_interval_seconds=0,
        )

        host1 = await manager.acquire(URL)
        host2 = await manager.acquire(URL)

        third = asyncio.create_task(manager.acquire(URL))

        await asyncio.sleep(0.02)

        # Both slots are occupied.
        self.assertFalse(third.done())

        # Free one slot.
        manager.release(host1)

        host3 = await asyncio.wait_for(
            third,
            timeout=1,
        )

        self.assertEqual(host3, host1)

        manager.release(host2)
        manager.release(host3)

    async def test_peak_concurrency_never_exceeds_limit(self):
        manager = PolitenessManager(
            max_concurrent_per_host=2,
            min_interval_seconds=0,
        )

        active = 0
        peak = 0

        async def worker():
            nonlocal active, peak

            async with manager.polite_slot(URL):
                active += 1
                peak = max(peak, active)

                try:
                    await asyncio.sleep(0.02)
                finally:
                    active -= 1

        await asyncio.gather(
            *(worker() for _ in range(10))
        )

        self.assertEqual(peak, 2)
        self.assertEqual(active, 0)

    async def test_different_hosts_run_independently(self):
        manager = PolitenessManager(
            max_concurrent_per_host=1,
            min_interval_seconds=0,
        )

        python_host = await manager.acquire(URL)

        # Python's slot is occupied, but MDN has its own.
        mdn_host = await asyncio.wait_for(
            manager.acquire(OTHER_URL),
            timeout=1,
        )

        self.assertNotEqual(python_host, mdn_host)

        manager.release(python_host)
        manager.release(mdn_host)

    # ------------------------------------------------------
    # TIMING RESTRICTIONS
    # ------------------------------------------------------

    async def test_minimum_interval(self):
        host = await self.manager.acquire(URL)
        self.manager.release(host)

        start = time.monotonic()

        host = await self.manager.acquire(URL)

        elapsed = time.monotonic() - start

        self.manager.release(host)

        print(f"\nMinimum interval: {elapsed:.3f}s")

        self.assertGreaterEqual(elapsed, 0.04)

    async def test_zero_interval(self):
        manager = PolitenessManager(
            min_interval_seconds=0,
        )

        host = await manager.acquire(URL)
        manager.release(host)

        host = await asyncio.wait_for(
            manager.acquire(URL),
            timeout=1,
        )

        manager.release(host)

    # ------------------------------------------------------
    # BACKOFF
    # ------------------------------------------------------

    async def test_apply_backoff(self):
        manager = PolitenessManager(
            min_interval_seconds=0,
            max_backoff_seconds=0.2,
        )

        await manager.apply_backoff(URL, 0.06)

        start = time.monotonic()

        host = await manager.acquire(URL)

        elapsed = time.monotonic() - start

        manager.release(host)

        print(f"\nBackoff wait: {elapsed:.3f}s")

        self.assertGreaterEqual(elapsed, 0.05)

    async def test_backoff_does_not_shorten(self):
        await self.manager.apply_backoff(URL, 0.12)

        state = self.manager._get_host_state(
            get_host_key(URL)
        )

        original_deadline = state.backoff_until

        await self.manager.apply_backoff(URL, 0.01)

        self.assertGreaterEqual(
            state.backoff_until,
            original_deadline,
        )

    async def test_backoff_is_capped(self):
        await self.manager.apply_backoff(URL, 1000)

        state = self.manager._get_host_state(
            get_host_key(URL)
        )

        remaining = (
            state.backoff_until - time.monotonic()
        )

        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 0.15)

    async def test_invalid_backoff(self):
        invalid_values = [
            -1,
            math.nan,
            math.inf,
            True,
        ]

        for seconds in invalid_values:
            with self.subTest(seconds=seconds):
                with self.assertRaises(ValueError):
                    await self.manager.apply_backoff(
                        URL, seconds
                    )

    # ------------------------------------------------------
    # HTTP RESPONSE HANDLING
    # ------------------------------------------------------

    async def test_429_triggers_backoff(self):
        await self.manager.record_response(
            URL,
            status_code=429,
            retry_after="30",
        )

        state = self.manager._get_host_state(
            get_host_key(URL)
        )

        self.assertGreater(
            state.backoff_until,
            time.monotonic(),
        )

    async def test_503_triggers_backoff(self):
        await self.manager.record_response(
            URL,
            status_code=503,
        )

        state = self.manager._get_host_state(
            get_host_key(URL)
        )

        self.assertGreater(
            state.backoff_until,
            time.monotonic(),
        )

    async def test_200_does_not_trigger_backoff(self):
        await self.manager.record_response(
            URL,
            status_code=200,
        )

        self.assertEqual(self.manager._states, {})

    async def test_invalid_retry_after_uses_default(self):
        await self.manager.record_response(
            URL,
            status_code=429,
            retry_after="invalid-date",
        )

        state = self.manager._get_host_state(
            get_host_key(URL)
        )

        remaining = (
            state.backoff_until - time.monotonic()
        )

        self.assertGreater(remaining, 0)
        self.assertLessEqual(remaining, 0.05)

    # ------------------------------------------------------
    # RELEASE AND ERROR HANDLING
    # ------------------------------------------------------

    async def test_release_unknown_host(self):
        with self.assertRaises(ValueError):
            self.manager.release("unknown.example")

    async def test_double_release_raises_error(self):
        host = await self.manager.acquire(URL)

        self.manager.release(host)

        with self.assertRaises(ValueError):
            self.manager.release(host)

    async def test_context_manager_releases_on_error(self):
        manager = PolitenessManager(
            max_concurrent_per_host=1,
            min_interval_seconds=0,
        )

        with self.assertRaises(RuntimeError):
            async with manager.polite_slot(URL):
                raise RuntimeError("Simulated fetch failure")

        # This would hang if the slot had leaked.
        host = await asyncio.wait_for(
            manager.acquire(URL),
            timeout=1,
        )

        manager.release(host)

    async def test_cancellation_releases_semaphore(self):
        manager = PolitenessManager(
            max_concurrent_per_host=1,
            min_interval_seconds=0.1,
        )

        first_host = await manager.acquire(URL)
        manager.release(first_host)

        # This task gets the semaphore but has to wait
        # for the minimum interval.
        waiting = asyncio.create_task(
            manager.acquire(URL)
        )

        await asyncio.sleep(0.01)

        self.assertFalse(waiting.done())

        waiting.cancel()

        with self.assertRaises(asyncio.CancelledError):
            await waiting

        # The cancelled task must have released its slot.
        host = await asyncio.wait_for(
            manager.acquire(URL),
            timeout=1,
        )

        manager.release(host)


# ==========================================================
# RUN ALL TESTS
# ==========================================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
