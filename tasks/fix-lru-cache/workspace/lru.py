class LRUCache:
    """A fixed-capacity cache that evicts the least-recently-used entry.

    Recency is updated on every get() and put(): touching a key makes it the
    most-recently used, so it should be the last to be evicted.
    """

    def __init__(self, capacity):
        self.capacity = capacity
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def put(self, key, value):
        if key in self.store:
            self.store[key] = value
            return
        if len(self.store) >= self.capacity:
            oldest = next(iter(self.store))
            del self.store[oldest]
        self.store[key] = value
