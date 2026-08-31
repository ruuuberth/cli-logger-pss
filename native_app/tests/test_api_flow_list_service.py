from __future__ import annotations

from datetime import datetime

from app.services.api_flow_list_service import ApiFlowListService
from app.services.api_flow_storage import BattleReplayListRow


class _Repo:
    def __init__(self) -> None:
        self.last_args = None

    def list_battle_replay_rows(self, search: str, page: int, page_size: int, **kwargs):
        self.last_args = (search, page, page_size)
        return 1, [
            BattleReplayListRow(
                id=11,
                api_flow_event_id=22,
                captured_at=datetime.fromisoformat("2026-02-20T10:00:00"),
                attacker_name="lord stella",
                attacker_trophy=5327,
                defender_name="Ruuuberth4",
                defender_trophy=5023,
                outcome_type="Attacker Won",
                win_minerals_result=100,
                lose_minerals_result=0,
                win_gas_result=50,
                lose_gas_result=0,
                win_trophy_result=15,
                lose_trophy_result=0,
                battle_id=99,
                attacker_user_id=10,
                defender_user_id=20,
            )
        ]

    def get_matchup_summaries_for_pairs(self, pairs: set[tuple[int, int]]):
        assert pairs == {(10, 20)}
        return {
            (10, 20): {
                "player_low_user_id": 10,
                "player_high_user_id": 20,
                "player_low_name": "lord stella",
                "player_high_name": "Ruuuberth4",
                "total_battles": 7,
                "player_low_wins": 4,
                "player_high_wins": 2,
                "unknown_results": 1,
                "last_battle_id": 99,
                "last_winner_user_id": 10,
                "last_captured_at": "2026-02-20T10:00:00",
                "recent_log": [
                    {"battle_id": 99, "winner_user_id": 10},
                    {"battle_id": 98, "winner_user_id": 20},
                    {"battle_id": 97, "winner_user_id": None},
                ],
            }
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
    assert row.h2h_label == "A 4 | D 2 | U 1"
    assert "H2H: lord stella vs Ruuuberth4" in row.h2h_tooltip
    assert "#99 -> lord stella" in row.h2h_tooltip


def test_h2h_fallback_when_ids_missing() -> None:
    class _RepoMissingIds(_Repo):
        def list_battle_replay_rows(self, search: str, page: int, page_size: int, **kwargs):
            self.last_args = (search, page, page_size)
            return 1, [
                BattleReplayListRow(
                    id=1,
                    api_flow_event_id=2,
                    captured_at=datetime.fromisoformat("2026-02-20T10:00:00"),
                    attacker_name="A",
                    attacker_trophy=1,
                    defender_name="B",
                    defender_trophy=2,
                    outcome_type="Attacker Won",
                    win_minerals_result=0,
                    lose_minerals_result=0,
                    win_gas_result=0,
                    lose_gas_result=0,
                    win_trophy_result=0,
                    lose_trophy_result=0,
                    battle_id=7,
                    attacker_user_id=None,
                    defender_user_id=20,
                )
            ]

        def get_matchup_summaries_for_pairs(self, pairs: set[tuple[int, int]]):
            assert pairs == set()
            return {}

    service = ApiFlowListService(repository=_RepoMissingIds())
    page = service.list_page("", 0, 50)
    row = page.rows[0]
    assert row.h2h_label == "-"
    assert row.h2h_tooltip == "Sin datos H2H"


def test_h2h_reorients_when_attacker_is_high_player() -> None:
    class _RepoSwapped(_Repo):
        def list_battle_replay_rows(self, search: str, page: int, page_size: int, **kwargs):
            self.last_args = (search, page, page_size)
            return 1, [
                BattleReplayListRow(
                    id=21,
                    api_flow_event_id=22,
                    captured_at=datetime.fromisoformat("2026-02-20T10:00:00"),
                    attacker_name="High",
                    attacker_trophy=1,
                    defender_name="Low",
                    defender_trophy=2,
                    outcome_type="Defender Won",
                    win_minerals_result=0,
                    lose_minerals_result=0,
                    win_gas_result=0,
                    lose_gas_result=0,
                    win_trophy_result=0,
                    lose_trophy_result=0,
                    battle_id=100,
                    attacker_user_id=20,
                    defender_user_id=10,
                )
            ]

    service = ApiFlowListService(repository=_RepoSwapped())
    page = service.list_page("", 0, 10)
    row = page.rows[0]
    assert row.h2h_label == "A 2 | D 4 | U 1"


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
