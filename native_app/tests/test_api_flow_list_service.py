from __future__ import annotations

from app.services.api_flow_list_service import ApiFlowListService


class _Repo:
    def __init__(self) -> None:
        self.last_args = None

    def list_battle_replays(self, search: str, page: int, page_size: int) -> dict:
        self.last_args = (search, page, page_size)
        return {
            "total": 1,
            "rows": [
                {
                    "id": 11,
                    "api_flow_event_id": 22,
                    "captured_at": "2026-02-20T10:00:00",
                    "attacker_name": "lord stella",
                    "attacker_trophy": 5327,
                    "defender_name": "Ruuuberth4",
                    "defender_trophy": 5023,
                    "outcome_type": "Attacker Won",
                    "win_minerals_result": 100,
                    "lose_minerals_result": 0,
                    "win_gas_result": 50,
                    "lose_gas_result": 0,
                    "win_trophy_result": 15,
                    "lose_trophy_result": 0,
                    "battle_id": 99,
                }
            ],
        }

    def delete_event(self, event_id: int) -> int:
        return 1 if event_id == 22 else 0

    def clear_events(self) -> int:
        return 10

    def clear_battle_replays(self) -> int:
        return 8

    def get_battle_replay_detail(self, battle_replay_id: int) -> dict | None:
        return {"id": battle_replay_id}


def test_list_page_formats_labels() -> None:
    repo = _Repo()
    service = ApiFlowListService(repository=repo)

    page = service.list_page("  ruu ", 2, 50)

    assert repo.last_args == ("ruu", 2, 50)
    assert page.total == 1
    assert page.max_page == 0
    row = page.rows[0]
    assert row.attacker_label == "(5327)lord stella"
    assert row.defender_label == "(5023)Ruuuberth4"
    assert row.loot_label == "M 100/0 | G 50/0"
    assert row.trophy_delta_label == "15/0"
    assert row.battle_id_label == "99"


def test_delete_event_delegates_to_repo() -> None:
    service = ApiFlowListService(repository=_Repo())
    assert service.delete_event(22) == 1
    assert service.delete_event(None) == 0


def test_clear_history_returns_both_counts() -> None:
    service = ApiFlowListService(repository=_Repo())
    result = service.clear_history()
    assert result.deleted_events == 10
    assert result.deleted_replays == 8


def test_get_battle_detail_delegates() -> None:
    service = ApiFlowListService(repository=_Repo())
    assert service.get_battle_detail(11) == {"id": 11}
