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
    h2h_label: str
    h2h_tooltip: str


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
        pairs = {
            self._pair_key(row.attacker_user_id, row.defender_user_id)
            for row in raw_rows
        }
        pairs = {pair for pair in pairs if pair is not None}
        matchup_summaries = self.repository.get_matchup_summaries_for_pairs(pairs)
        rows = [self._to_row_view(row, matchup_summaries) for row in raw_rows]
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

    def _to_row_view(
        self,
        row: BattleReplayListRow,
        matchup_summaries: dict[tuple[int, int], dict],
    ) -> ApiFlowRowView:
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
        h2h_label, h2h_tooltip = self._build_h2h_labels(
            row,
            matchup_summaries.get(self._pair_key(row.attacker_user_id, row.defender_user_id)),
        )
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
            h2h_label=h2h_label,
            h2h_tooltip=h2h_tooltip,
        )

    def _pair_key(self, attacker_user_id: int | None, defender_user_id: int | None) -> tuple[int, int] | None:
        if attacker_user_id is None or defender_user_id is None:
            return None
        if attacker_user_id == defender_user_id:
            return None
        return (
            (attacker_user_id, defender_user_id)
            if attacker_user_id < defender_user_id
            else (defender_user_id, attacker_user_id)
        )

    def _build_h2h_labels(
        self,
        row: BattleReplayListRow,
        summary: dict | None,
    ) -> tuple[str, str]:
        if summary is None:
            return "-", "Sin datos H2H"

        attacker_id = row.attacker_user_id
        defender_id = row.defender_user_id
        if attacker_id is None or defender_id is None:
            return "-", "Sin datos H2H"

        low_id = summary.get("player_low_user_id")
        high_id = summary.get("player_high_user_id")
        low_name = str(summary.get("player_low_name") or row.attacker_name or f"User {low_id or '-'}")
        high_name = str(summary.get("player_high_name") or row.defender_name or f"User {high_id or '-'}")
        low_wins = int(summary.get("player_low_wins") or 0)
        high_wins = int(summary.get("player_high_wins") or 0)
        unknown = int(summary.get("unknown_results") or 0)
        total = int(summary.get("total_battles") or 0)

        if attacker_id == low_id and defender_id == high_id:
            attacker_wins = low_wins
            defender_wins = high_wins
            attacker_name = low_name
            defender_name = high_name
        elif attacker_id == high_id and defender_id == low_id:
            attacker_wins = high_wins
            defender_wins = low_wins
            attacker_name = high_name
            defender_name = low_name
        else:
            attacker_wins = 0
            defender_wins = 0
            attacker_name = str(row.attacker_name or f"User {attacker_id}")
            defender_name = str(row.defender_name or f"User {defender_id}")

        label = f"A {attacker_wins} | D {defender_wins} | U {unknown}"
        lines = [
            f"H2H: {attacker_name} vs {defender_name}",
            f"Total: {total} | A: {attacker_wins} | D: {defender_wins} | U: {unknown}",
        ]
        recent = summary.get("recent_log")
        if isinstance(recent, list) and recent:
            lines.append("Ultimos 5:")
            for item in recent[:5]:
                winner = item.get("winner_user_id")
                if winner == attacker_id:
                    winner_label = attacker_name
                elif winner == defender_id:
                    winner_label = defender_name
                elif winner == low_id:
                    winner_label = low_name
                elif winner == high_id:
                    winner_label = high_name
                elif winner is None:
                    winner_label = "Desconocido"
                else:
                    winner_label = f"User {winner}"
                lines.append(f"#{item.get('battle_id') or '-'} -> {winner_label}")
        return label, "\n".join(lines)
