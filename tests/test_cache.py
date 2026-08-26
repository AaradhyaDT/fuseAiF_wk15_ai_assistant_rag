from app.cache import TTLCache


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_hit_miss_and_expiry():
    clock = FakeClock()
    cache = TTLCache(ttl_s=10, max_items=8, clock=clock)
    key = TTLCache.make_key("prompt-a")
    cache.put(key, {"answer": "42"})
    assert cache.get(key) == {"answer": "42"}
    clock.t += 11
    assert cache.get(key) is None


def test_lru_eviction():
    cache = TTLCache(ttl_s=100, max_items=2, clock=FakeClock())
    for label in "abc":
        cache.put(TTLCache.make_key(label), label)
    assert cache.get(TTLCache.make_key("a")) is None
    assert cache.get(TTLCache.make_key("c")) == "c"


def test_key_is_stable_and_order_insensitive():
    k1 = TTLCache.make_key({"a": 1, "b": [1, 2]})
    k2 = TTLCache.make_key({"b": [1, 2], "a": 1})
    assert k1 == k2
    assert len(k1) == 64
