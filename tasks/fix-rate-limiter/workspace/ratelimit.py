class TokenBucket:
    """A token-bucket rate limiter.

    The bucket starts full with `capacity` tokens and gains `refill_rate` tokens
    per unit of time, but never more than `capacity`. allow(now) refills based on
    the time elapsed since the last call, then consumes one token if available.
    Returns True if the request is allowed, False otherwise. `now` is a monotonic
    timestamp passed in by the caller (so behavior is deterministic).
    """

    def __init__(self, capacity, refill_rate):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last = 0

    def allow(self, now):
        elapsed = now - self.last
        self.last = now
        self.tokens = self.tokens + elapsed * self.refill_rate
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False
