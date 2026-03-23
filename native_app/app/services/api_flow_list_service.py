from __future__ import annotations

from dataclasses import dataclass
import logging

from app.services.battle_detail_cache import BattleDetailCache
from app.services.perf_metrics import measure_perf
from app.services.api_flow_storage import ApiFlowRepository, BattleReplayListRow


@dataclass(frozen=True)
class ApiFlowRowView:
    battle_replay_id: int | None
    api_flow_event_id: int | None
    captured_at_label: str
    attacker_label: str
    defender_label: str
    outcome_label: str
    loot_label: str
    trophy_delta_label: str
    battle_id_label: str


@dataclass(frozen=True)
class ApiFlowPage:
    total: int
    page: int
    max_page: int
    rows: list[ApiFlowRowView]


@dataclass(frozen=True)
class ApiFlowClearResult:
    deleted_events: int
    deleted_replays: int


class ApiFlowListService:
    def __init__(
        self,
        repository: ApiFlowRepository | None = None,
        detail_cache: BattleDetailCache | None = None,
    ) -> None:
        self.repository = repository or ApiFlowRepository()
        self.detail_cache = detail_cache or BattleDetailCache()
        self.logger = logging.getLogger(__name__)

    def list_page(self, search: str, page: int, page_size: int) -> ApiFlowPage:
        with measure_perf("api_flow_list_page", self.logger):
            total, raw_rows = self.repository.list_battle_replay_rows(
                search=search.strip(),
                page=page,
                page_size=page_size,
            )
        rows = [self._to_row_view(row) for row in raw_rows]
        max_page = max(0, (total - 1) // page_size) if total else 0
        return ApiFlowPage(total=total, page=page, max_page=max_page, rows=rows)

    def delete_event(self, event_id: int | None) -> int:
        if event_id is None:
            return 0
        deleted = self.repository.delete_event(int(event_id))
        if deleted > 0:
            self.detail_cache.invalidate()
        return deleted

    def clear_history(self) -> ApiFlowClearResult:
        deleted_events = self.repository.clear_events()
        deleted_replays = self.repository.clear_battle_replays()
        self.detail_cache.invalidate()
        return ApiFlowClearResult(
            deleted_events=deleted_events,
            deleted_replays=deleted_replays,
        )

    def get_battle_detail(self, battle_replay_id: int) -> dict | None:
        cached = self.detail_cache.get(battle_replay_id)
        if cached is not None:
            return cached
        with measure_perf("battle_replay_detail", self.logger):
            detail = self.repository.get_battle_replay_detail(battle_replay_id)
        if detail is not None:
            self.detail_cache.set(battle_replay_id, detail)
        return detail

    def _to_row_view(self, row: BattleReplayListRow) -> ApiFlowRowView:
        captured_at = str(row.captured_at or "")[:19].replace("T", " ")
        attacker_name = str(row.attacker_name or "-")
        defender_name = str(row.defender_name or "-")
        attacker = f"({row.attacker_trophy or 0}){attacker_name}"
        defender = f"({row.defender_trophy or 0}){defender_name}"
        loot = (
            f"M {row.win_minerals_result or 0}/{row.lose_minerals_result or 0}"
            f" | G {row.win_gas_result or 0}/{row.lose_gas_result or 0}"
        )
        trophies = f"{row.win_trophy_result or 0}/{row.lose_trophy_result or 0}"
        return ApiFlowRowView(
            battle_replay_id=row.id,
            api_flow_event_id=row.api_flow_event_id,
            captured_at_label=captured_at,
            attacker_label=attacker,
            defender_label=defender,
            outcome_label=str(row.outcome_type or "-"),
            loot_label=loot,
            trophy_delta_label=trophies,
            battle_id_label=str(row.battle_id or "-"),
        )
