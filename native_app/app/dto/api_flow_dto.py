"""Pure data structures for API flow events (no Qt dependencies)"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ApiFlowRowDTO:
    """Represents a single API flow event row in pure Python"""
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

    @classmethod
    def from_service_model(cls, row_view: "ApiFlowRowView") -> "ApiFlowRowDTO":
        """Convert from service ApiFlowRowView to pure DTO"""
        return cls(
            battle_replay_id=row_view.battle_replay_id,
            api_flow_event_id=row_view.api_flow_event_id,
            captured_at_label=row_view.captured_at_label,
            attacker_label=row_view.attacker_label,
            defender_label=row_view.defender_label,
            outcome_label=row_view.outcome_label,
            loot_label=row_view.loot_label,
            trophy_delta_label=row_view.trophy_delta_label,
            battle_id_label=row_view.battle_id_label,
            h2h_label=row_view.h2h_label,
            h2h_tooltip=row_view.h2h_tooltip,
        )


@dataclass(frozen=True)
class ApiFlowPageDTO:
    """Represents a page of API flow events"""
    total: int
    page: int
    max_page: int
    rows: list[ApiFlowRowDTO]

    @classmethod
    def from_service_model(cls, page: "ApiFlowPage") -> "ApiFlowPageDTO":
        """Convert from service ApiFlowPage to pure DTO"""
        return cls(
            total=page.total,
            page=page.page,
            max_page=page.max_page,
            rows=[ApiFlowRowDTO.from_service_model(row) for row in page.rows],
        )


@dataclass(frozen=True)
class BattleDetailDTO:
    """Represents detailed battle information"""
    battle_id: str
    attacker_name: str
    defender_name: str
    outcome: str
    loot: str
    trophy_delta: int
    captured_at: str
    raw_data: dict  # Raw JSON data from database


@dataclass(frozen=True)
class CaptureStatsDTO:
    """Represents live capture statistics"""
    events_total: int
    events_per_second: float
    uptime_seconds: int
    is_capturing: bool
    proxy_running: bool
