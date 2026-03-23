from __future__ import annotations

from dataclasses import dataclass

from app.services.api_flow_storage import ApiFlowRepository


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
    def __init__(self, repository: ApiFlowRepository | None = None) -> None:
        self.repository = repository or ApiFlowRepository()

    def list_page(self, search: str, page: int, page_size: int) -> ApiFlowPage:
        payload = self.repository.list_battle_replays(
            search=search.strip(),
            page=page,
            page_size=page_size,
        )
        total = int(payload["total"])
        rows = [self._to_row_view(row) for row in payload["rows"]]
        max_page = max(0, (total - 1) // page_size) if total else 0
        return ApiFlowPage(total=total, page=page, max_page=max_page, rows=rows)

    def delete_event(self, event_id: int | None) -> int:
        if event_id is None:
            return 0
        return self.repository.delete_event(int(event_id))

    def clear_history(self) -> ApiFlowClearResult:
        deleted_events = self.repository.clear_events()
        deleted_replays = self.repository.clear_battle_replays()
        return ApiFlowClearResult(
            deleted_events=deleted_events,
            deleted_replays=deleted_replays,
        )

    def get_battle_detail(self, battle_replay_id: int) -> dict | None:
        return self.repository.get_battle_replay_detail(battle_replay_id)

    def _to_row_view(self, row: dict) -> ApiFlowRowView:
        captured_at = str(row.get("captured_at") or "")[:19].replace("T", " ")
        attacker_name = str(row.get("attacker_name") or "-")
        defender_name = str(row.get("defender_name") or "-")
        attacker = f"({row.get('attacker_trophy') or 0}){attacker_name}"
        defender = f"({row.get('defender_trophy') or 0}){defender_name}"
        loot = (
            f"M {row.get('win_minerals_result') or 0}/{row.get('lose_minerals_result') or 0}"
            f" | G {row.get('win_gas_result') or 0}/{row.get('lose_gas_result') or 0}"
        )
        trophies = f"{row.get('win_trophy_result') or 0}/{row.get('lose_trophy_result') or 0}"
        return ApiFlowRowView(
            battle_replay_id=row.get("id"),
            api_flow_event_id=row.get("api_flow_event_id"),
            captured_at_label=captured_at,
            attacker_label=attacker,
            defender_label=defender,
            outcome_label=str(row.get("outcome_type") or "-"),
            loot_label=loot,
            trophy_delta_label=trophies,
            battle_id_label=str(row.get("battle_id") or "-"),
        )
