"""Tests for the H2H trend bucket (day/week) wiring — issue #11.

Covers:
- ApiFlowListService.get_h2h_report_data forwards ``trend_bucket`` to the
  repository's ``get_h2h_trends`` (keyword-only param).
- ApiFlowCliService.get_h2h_report_data forwards the bucket verbatim.
- GenerateH2HReportCommand prompt normalization (semana/week/w -> "week",
  anything else -> "day"), via the ``--trend-bucket`` option.
- End-to-end: a week bucket produces ``YYYY-Www`` periods in the trends data
  and those periods render verbatim in H2HReportTemplate.trend_rows.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.cli.concrete_commands import GenerateH2HReportCommand
from app.cli.cli_services import ApiFlowCliService
from app.models.database import Base
from app.models.pss_models import ApiFlowEvent, BattleReplayNormalized, PlayerMatchupLog
from app.reporting.report_templates import H2HReportTemplate
from app.services.api_flow_list_service import ApiFlowListService
import app.services.api_flow_storage as storage_module


# ---------------------------------------------------------------------------
# Service layer: bucket forwarding
# ---------------------------------------------------------------------------

class _RecordingRepo:
    """Minimal repository double that records the bucket it was called with."""

    def __init__(self):
        self.trend_buckets: list[str] = []

    def get_h2h_summary(self, low_user_id, high_user_id, date_from=None, date_to=None, outcome=None):
        return {
            "player_low_user_id": low_user_id,
            "player_high_user_id": high_user_id,
            "player_low_name": "PlayerA",
            "player_high_name": "PlayerB",
            "total_battles": 1,
            "player_low_wins": 1,
            "player_high_wins": 0,
            "unknown_results": 0,
            "first_battle_date": datetime.fromisoformat("2026-01-01T10:00:00"),
            "last_battle_date": datetime.fromisoformat("2026-01-01T10:00:00"),
        }

    def get_h2h_battles(self, low_user_id, high_user_id, date_from=None, date_to=None, outcome=None, limit=1000):
        return []

    def get_h2h_trends(self, low_user_id, high_user_id, date_from=None, date_to=None, outcome=None, bucket="day"):
        self.trend_buckets.append(bucket)
        return [
            {
                "period": "2026-W01",
                "battle_count": 1,
                "player_low_wins": 1,
                "player_high_wins": 0,
                "player_low_avg_trophies": 5000,
                "player_high_avg_trophies": 4800,
            }
        ]

    def get_h2h_fleet_breakdown(self, low_user_id, high_user_id, date_from=None, date_to=None, outcome=None, limit=1000):
        return None


def test_list_service_forwards_trend_bucket_to_repo() -> None:
    repo = _RecordingRepo()
    service = ApiFlowListService(repository=repo)

    # default: no explicit bucket -> repo still receives "day"
    service.get_h2h_report_data(10, 20)
    assert repo.trend_buckets == ["day"]

    # explicit week bucket is forwarded verbatim
    service.get_h2h_report_data(10, 20, trend_bucket="week")
    assert repo.trend_buckets == ["day", "week"]


def test_cli_service_forwards_trend_bucket_verbatim() -> None:
    captured: dict[str, object] = {}

    class _StubListService:
        def get_h2h_report_data(self, low_user_id, high_user_id, date_from=None, date_to=None, outcome=None, limit=1000, *, trend_bucket="day"):
            captured["trend_bucket"] = trend_bucket
            return None

    cli_service = ApiFlowCliService()
    cli_service.list_service = _StubListService()

    cli_service.get_h2h_report_data(10, 20)
    assert captured["trend_bucket"] == "day"

    cli_service.get_h2h_report_data(10, 20, trend_bucket="week")
    assert captured["trend_bucket"] == "week"


# ---------------------------------------------------------------------------
# Command layer: prompt/option normalization
# ---------------------------------------------------------------------------

def _make_command() -> tuple[GenerateH2HReportCommand, _RecordingRepo]:
    """Build a GenerateH2HReportCommand with stubbed pair selection + service."""
    cmd = GenerateH2HReportCommand(runtime=None)
    repo = _RecordingRepo()
    list_service = ApiFlowListService(repository=repo)
    cmd.service = list_service  # replace facade with a direct list service
    cmd._select_pair_from_list = lambda: {  # type: ignore[method-assign]
        "low_user_id": 10,
        "high_user_id": 20,
        "low_name": "PlayerA",
        "high_name": "PlayerB",
    }
    return cmd, repo


def _run_json_report(cmd: GenerateH2HReportCommand, args: list[str], tmp_path) -> dict:
    """Run the command non-interactively with JSON output; return the parsed report."""
    import json

    full_args = ["--method=1", "--non-interactive", "--format=json", f"--output-dir={tmp_path}", "--no-timestamp"]
    full_args.extend(args)

    rc = cmd.execute(full_args)
    assert rc == 0, "command should succeed"

    report_path = tmp_path / "h2h_playera_vs_playerb.json"
    assert report_path.exists(), f"report file missing: {tmp_path.listdir() if hasattr(tmp_path, 'listdir') else 'check dir'}"
    with open(report_path, encoding="utf-8") as f:
        return json.load(f)


def test_command_trend_bucket_option_normalization(tmp_path) -> None:
    # "week" passes through
    cmd, repo = _make_command()
    _run_json_report(cmd, ["--trend-bucket=week"], tmp_path)
    assert repo.trend_buckets == ["week"]

    # "semana" normalizes to "week"
    cmd2, repo2 = _make_command()
    _run_json_report(cmd2, ["--trend-bucket=semana"], tmp_path)
    assert repo2.trend_buckets == ["week"]

    # "w" normalizes to "week"
    cmd3, repo3 = _make_command()
    _run_json_report(cmd3, ["--trend-bucket=w"], tmp_path)
    assert repo3.trend_buckets == ["week"]

    # unknown value falls back to "day"
    cmd4, repo4 = _make_command()
    _run_json_report(cmd4, ["--trend-bucket=mes"], tmp_path)
    assert repo4.trend_buckets == ["day"]

    # no option -> default "day"
    cmd5, repo5 = _make_command()
    _run_json_report(cmd5, [], tmp_path)
    assert repo5.trend_buckets == ["day"]


# ---------------------------------------------------------------------------
# End-to-end: week bucket renders YYYY-Www in trend rows
# ---------------------------------------------------------------------------

def _build_repo(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(storage_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(storage_module, "engine", test_engine)
    return storage_module.ApiFlowRepository(), TestingSessionLocal


def _insert_matchup(db, *, battle_id: int, winner_user_id: int, captured_at: datetime) -> None:
    event = ApiFlowEvent(
        session_id="s1",
        captured_at=captured_at,
        direction="response",
        path="/BattleService/GetBattle3",
    )
    db.add(event)
    db.flush()
    replay = BattleReplayNormalized(
        api_flow_event_id=event.id,
        battle_id=battle_id,
        captured_at=captured_at,
        attacker_user_id=10,
        attacker_name="PlayerA",
        defender_user_id=20,
        defender_name="PlayerB",
        outcome_type="Attacker Won",
    )
    db.add(replay)
    db.flush()
    db.add(PlayerMatchupLog(
        player_low_user_id=10,
        player_high_user_id=20,
        battle_id=battle_id,
        winner_user_id=winner_user_id,
        outcome_type="Attacker Won",
        captured_at=captured_at,
        source_battle_replay_id=replay.id,
        source_api_flow_event_id=event.id,
    ))


def test_week_bucket_renders_week_periods_end_to_end(monkeypatch, tmp_path) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)

    # Two battles in different weeks of January 2026 (both Sundays: %U increments on Sunday)
    base = datetime(2026, 1, 4, 12, 0, 0, tzinfo=timezone.utc)  # a Sunday
    week1_day = base                        # 2026-01-04 -> %U week 0 (Jan 1 is Thursday)
    week2_day = base + timedelta(days=7)    # 2026-01-11 -> %U week 1

    db = SessionLocal()
    _insert_matchup(db, battle_id=201, winner_user_id=10, captured_at=week1_day)
    _insert_matchup(db, battle_id=202, winner_user_id=20, captured_at=week2_day)
    db.commit()
    db.close()

    # Service layer with week bucket against the real repo
    service = ApiFlowListService(repository=repo)
    h2h_data = service.get_h2h_report_data(10, 20, trend_bucket="week")

    assert h2h_data is not None
    trends = h2h_data["trends"]
    assert len(trends) == 2
    periods = [t["period"] for t in trends]
    # periods must match the exact "YYYY-Www" shape the repo's strftime produces
    assert periods == [week1_day.strftime("%Y-W%U"), week2_day.strftime("%Y-W%U")]
    # and the format is literally year + "-W" + two-digit week number
    for p in periods:
        year, week = p.split("-W")
        assert len(year) == 4 and year.isdigit()
        assert len(week) == 2 and week.isdigit()

    # Rendering: trend_rows passes the period through verbatim
    rows = H2HReportTemplate.trend_rows(h2h_data)
    assert len(rows) == 2
    assert [r["Periodo"] for r in rows] == periods

    # Day bucket still renders per-day periods
    h2h_day = service.get_h2h_report_data(10, 20, trend_bucket="day")
    assert h2h_day is not None
    assert [t["period"] for t in h2h_day["trends"]] == ["2026-01-04", "2026-01-11"]
