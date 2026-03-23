from __future__ import annotations

from collections import OrderedDict
from typing import Any


class BattleDetailCache:
    def __init__(self, max_entries: int = 16) -> None:
        self.max_entries = max(1, int(max_entries))
        self._entries: OrderedDict[int, dict[str, Any]] = OrderedDict()

    def get(self, battle_replay_id: int) -> dict[str, Any] | None:
        payload = self._entries.get(int(battle_replay_id))
        if payload is None:
            return None
        self._entries.move_to_end(int(battle_replay_id))
        return payload

    def set(self, battle_replay_id: int, payload: dict[str, Any]) -> None:
        key = int(battle_replay_id)
        self._entries[key] = payload
        self._entries.move_to_end(key)
        while len(self._entries) > self.max_entries:
            self._entries.popitem(last=False)

    def invalidate(self, battle_replay_id: int | None = None) -> None:
        if battle_replay_id is None:
            self._entries.clear()
            return
        self._entries.pop(int(battle_replay_id), None)
