from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.pss_models import PlayerMatchupLog, PlayerMatchupStat
import app.services.api_flow_storage as storage_module


def _build_repo(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(storage_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(storage_module, "engine", test_engine)
    return storage_module.ApiFlowRepository(), TestingSessionLocal


def test_get_matchup_summaries_for_pairs_returns_stats_and_recent(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    db.add(
        PlayerMatchupStat(
            player_low_user_id=10,
            player_high_user_id=20,
            player_low_name="Low",
            player_high_name="High",
            total_battles=3,
            player_low_wins=2,
            player_high_wins=1,
            unknown_results=0,
            last_battle_id=999,
            last_winner_user_id=10,
            last_captured_at=now,
        )
    )
    db.add_all(
        [
            PlayerMatchupLog(
                player_low_user_id=10,
                player_high_user_id=20,
                battle_id=999,
                winner_user_id=10,
                outcome_type="Attacker Won",
                captured_at=now,
            ),
            PlayerMatchupLog(
                player_low_user_id=10,
                player_high_user_id=20,
                battle_id=998,
                winner_user_id=20,
                outcome_type="Defender Won",
                captured_at=now - timedelta(minutes=1),
            ),
            PlayerMatchupLog(
                player_low_user_id=10,
                player_high_user_id=20,
                battle_id=997,
                winner_user_id=None,
                outcome_type="Unknown",
                captured_at=now - timedelta(minutes=2),
            ),
        ]
    )
    db.commit()
    db.close()

    out = repo.get_matchup_summaries_for_pairs({(10, 20), (30, 40)})

    assert (10, 20) in out
    assert (30, 40) not in out
    summary = out[(10, 20)]
    assert summary["total_battles"] == 3
    assert summary["player_low_wins"] == 2
    assert summary["player_high_wins"] == 1
    assert len(summary["recent_log"]) == 3
    assert summary["recent_log"][0]["battle_id"] == 999


def test_get_matchup_summaries_for_pairs_derives_when_stat_missing(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    db.add_all(
        [
            PlayerMatchupLog(
                player_low_user_id=11,
                player_high_user_id=22,
                battle_id=401,
                winner_user_id=11,
                outcome_type="Attacker Won",
                captured_at=now,
            ),
            PlayerMatchupLog(
                player_low_user_id=11,
                player_high_user_id=22,
                battle_id=400,
                winner_user_id=None,
                outcome_type="Unknown",
                captured_at=now - timedelta(minutes=1),
            ),
        ]
    )
    db.commit()
    db.close()

    out = repo.get_matchup_summaries_for_pairs({(11, 22)})
    summary = out[(11, 22)]
    assert summary["total_battles"] == 2
    assert summary["player_low_wins"] == 1
    assert summary["player_high_wins"] == 0
    assert summary["unknown_results"] == 1


def test_get_matchup_summaries_for_pairs_empty_input(monkeypatch) -> None:
    repo, _ = _build_repo(monkeypatch)
    assert repo.get_matchup_summaries_for_pairs(set()) == {}
