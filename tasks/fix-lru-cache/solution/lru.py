class LRUCache:
    """A fixed-capacity cache that evicts the least-recently-used entry.

    Recency is updated on every get() and put(): touching a key makes it the
    most-recently used, so it should be the last to be evicted.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.store = {}

    def get(self, key):
        if key not in self.store:
            return None
        value = self.store.pop(key)
        self.store[key] = value  # re-insert to mark most-recently used
        return value

    def put(self, key, value):
        if key in self.store:
            self.store.pop(key)
        elif len(self.store) >= self.capacity:
            oldest = next(iter(self.store))
            del self.store[oldest]
        self.store[key] = value
