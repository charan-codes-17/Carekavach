from collections import defaultdict

from fastapi import Request

from app.clock import Clock


def extract_client_ip(request: Request) -> str:
    """Extract client IP using first X-Forwarded-For component or client.host."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # First IP in comma-separated chain is the client IP
        first_ip = forwarded.split(",")[0].strip()
        if first_ip:
            return first_ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


class RateLimiter:
    """In-memory sliding-window rate limiter tracking failed attempts by IP and key."""

    def __init__(
        self,
        clock: Clock,
        max_attempts: int = 5,
        window_seconds: int = 300,  # 5 minutes
    ) -> None:
        self.clock = clock
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._ip_failures: dict[str, list[float]] = defaultdict(list)
        self._key_failures: dict[str, list[float]] = defaultdict(list)

    def _clean_and_count(self, timestamps: list[float], current_ts: float) -> tuple[int, int]:
        cutoff = current_ts - self.window_seconds
        # Retain only timestamps within the sliding window
        valid = [ts for ts in timestamps if ts > cutoff]
        timestamps.clear()
        timestamps.extend(valid)
        count = len(valid)
        if count >= self.max_attempts and valid:
            oldest_in_window = valid[0]
            retry_after = max(1, int(oldest_in_window + self.window_seconds - current_ts))
            return count, retry_after
        return count, 0

    def is_rate_limited(self, ip: str, key: str) -> tuple[bool, int]:
        """Check if either IP or key is rate-limited. Returns (is_limited, retry_after_seconds)."""
        current_ts = self.clock.now_utc().timestamp()
        norm_key = key.strip().lower()

        ip_count, ip_retry = self._clean_and_count(self._ip_failures[ip], current_ts)
        key_count, key_retry = self._clean_and_count(self._key_failures[norm_key], current_ts)

        if ip_count >= self.max_attempts or key_count >= self.max_attempts:
            retry_after = max(ip_retry, key_retry)
            return True, retry_after
        return False, 0

    def record_failure(self, ip: str, key: str) -> None:
        """Record a failure event for both IP and key."""
        current_ts = self.clock.now_utc().timestamp()
        norm_key = key.strip().lower()
        self._ip_failures[ip].append(current_ts)
        self._key_failures[norm_key].append(current_ts)

    def record_success(self, ip: str, key: str) -> None:
        """Reset failures for IP and key upon successful authentication."""
        norm_key = key.strip().lower()
        self._ip_failures.pop(ip, None)
        self._key_failures.pop(norm_key, None)
