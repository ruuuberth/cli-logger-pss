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


def test_get_h2h_report_data_delegates() -> None:
    class _RepoH2H(_Repo):
        def get_h2h_summary(self, low_user_id: int, high_user_id: int, date_from=None, date_to=None, outcome=None):
            assert low_user_id == 10
            assert high_user_id == 20
            return {
                "player_low_user_id": 10,
                "player_high_user_id": 20,
                "player_low_name": "PlayerA",
                "player_high_name": "PlayerB",
                "total_battles": 5,
                "player_low_wins": 3,
                "player_high_wins": 2,
                "unknown_results": 0,
                "first_battle_date": datetime.fromisoformat("2026-01-01T10:00:00"),
                "last_battle_date": datetime.fromisoformat("2026-01-05T10:00:00"),
            }

        def get_h2h_battles(self, low_user_id: int, high_user_id: int, date_from=None, date_to=None, outcome=None, limit=1000):
            return [
                {"captured_at": datetime.fromisoformat("2026-01-05T10:00:00"), "battle_id": 100, "attacker_name": "A", "defender_name": "B", "outcome": "Attacker Won", "attacker_trophy_delta": 10, "defender_trophy_delta": -5, "loot_minerals": "M 100/0", "loot_gas": "G 50/0"},
            ]

        def get_h2h_trends(self, low_user_id: int, high_user_id: int, date_from=None, date_to=None, outcome=None, bucket="day"):
            return [
                {"period": "2026-01-01", "battle_count": 2, "player_low_wins": 1, "player_high_wins": 1, "player_low_avg_trophies": 5000, "player_high_avg_trophies": 4800},
            ]

    service = ApiFlowListService(repository=_RepoH2H())
    data = service.get_h2h_report_data(10, 20)

    assert data is not None
    assert data["summary"]["total_battles"] == 5
    assert data["summary"]["player_low_wins"] == 3
    assert len(data["battles"]) == 1
    assert len(data["trends"]) == 1


def test_get_unique_player_pairs_delegates() -> None:
    class _RepoPairs(_Repo):
        def get_unique_player_pairs(self):
            return [{"low_user_id": 1, "high_user_id": 2, "low_name": "A", "high_name": "B", "total_battles": 3, "low_wins": 2, "high_wins": 1}]

    service = ApiFlowListService(repository=_RepoPairs())
    pairs = service.get_unique_player_pairs()
    assert len(pairs) == 1
    assert pairs[0]["low_user_id"] == 1


def test_search_player_pairs_delegates() -> None:
    class _RepoSearch(_Repo):
        def search_player_pairs(self, search: str):
            assert search == "player"
            return [{"low_user_id": 1, "high_user_id": 2, "low_name": "PlayerA", "high_name": "PlayerB", "total_battles": 3, "low_wins": 2, "high_wins": 1}]

    service = ApiFlowListService(repository=_RepoSearch())
    pairs = service.search_player_pairs("player")
    assert len(pairs) == 1
    assert pairs[0]["low_name"] == "PlayerA"
