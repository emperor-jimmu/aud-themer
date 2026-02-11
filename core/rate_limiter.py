"""Rate limiting utilities to prevent abuse and IP bans."""

import time
import random
from typing import Dict
from core.config import Config


class RateLimiter:
    """Implements rate limiting with random jitter between requests."""

    def __init__(
        self,
        min_delay: float = Config.RATE_LIMIT_MIN_DELAY_SEC,
        max_delay: float = Config.RATE_LIMIT_MAX_DELAY_SEC
    ):
        """
        Initialize rate limiter.

        Args:
            min_delay: Minimum delay in seconds between requests
            max_delay: Maximum delay in seconds between requests
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._last_attempt: Dict[str, float] = {}

    def wait(self, source_name: str) -> None:
        """
        Wait appropriate amount of time before next request to source.

        Uses random jitter to avoid thundering herd problems.

        Args:
            source_name: Name of the source/scraper
        """
        last_time = self._last_attempt.get(source_name)

        if last_time is not None:
            elapsed = time.time() - last_time
            delay = random.uniform(self.min_delay, self.max_delay)

            if elapsed < delay:
                sleep_time = delay - elapsed
                time.sleep(sleep_time)

        self._last_attempt[source_name] = time.time()

    def record_attempt(self, source_name: str) -> None:
        """
        Record an attempt to a source without waiting.

        Useful for recording attempts that happened outside the rate limiter.

        Args:
            source_name: Name of the source/scraper
        """
        self._last_attempt[source_name] = time.time()

    def reset(self, source_name: str = None) -> None:
        """
        Reset rate limiting state.

        Args:
            source_name: Specific source to reset, or None to reset all
        """
        if source_name:
            self._last_attempt.pop(source_name, None)
        else:
            self._last_attempt.clear()
