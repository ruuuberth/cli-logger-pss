from __future__ import annotations

from app.services.battle_detail_cache import BattleDetailCache


def test_cache_returns_recent_payload() -> None:
    cache = BattleDetailCache(max_entries=2)
    cache.set(10, {"id": 10})
    assert cache.get(10) == {"id": 10}


def test_cache_evicts_oldest_when_capacity_is_reached() -> None:
    cache = BattleDetailCache(max_entries=2)
    cache.set(1, {"id": 1})
    cache.set(2, {"id": 2})
    cache.set(3, {"id": 3})
    assert cache.get(1) is None
    assert cache.get(2) == {"id": 2}
    assert cache.get(3) == {"id": 3}


def test_cache_invalidate_specific_and_all() -> None:
    cache = BattleDetailCache(max_entries=2)
    cache.set(1, {"id": 1})
    cache.set(2, {"id": 2})
    cache.invalidate(1)
    assert cache.get(1) is None
    assert cache.get(2) == {"id": 2}
    cache.invalidate()
    assert cache.get(2) is None
