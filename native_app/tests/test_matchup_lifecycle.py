from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.pss_models import ApiFlowEvent, BattleReplayNormalized, PlayerMatchupLog, PlayerMatchupStat
import app.services.api_flow_storage as storage_module


def _build_repo(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(storage_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(storage_module, "engine", test_engine)
    return storage_module.ApiFlowRepository(), TestingSessionLocal


def _insert_replay(
    db,
    *,
    session_id: str,
    captured_at: datetime,
    battle_id: int,
    attacker_user_id: int,
    attacker_name: str,
    defender_user_id: int,
    defender_name: str,
    outcome_type: str,
):
    event = ApiFlowEvent(
        session_id=session_id,
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
        attacker_user_id=attacker_user_id,
        attacker_name=attacker_name,
        defender_user_id=defender_user_id,
        defender_name=defender_name,
        outcome_type=outcome_type,
    )
    db.add(replay)
    db.flush()
    return replay, event


def test_backfill_prunes_and_builds_stats(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s1",
        captured_at=now - timedelta(minutes=2),
        battle_id=101,
        attacker_user_id=10,
        attacker_name="Alice",
        defender_user_id=20,
        defender_name="Bob",
        outcome_type="Attacker Won",
    )
    _insert_replay(
        db,
        session_id="s1",
        captured_at=now - timedelta(minutes=1),
        battle_id=102,
        attacker_user_id=10,
        attacker_name="Alice",
        defender_user_id=20,
        defender_name="Bob",
        outcome_type="Defender Won",
    )
    db.commit()
    db.close()

    metrics = repo.backfill_matchup_history_and_prune()
    assert metrics["inserted_logs"] == 2
    assert metrics["deleted_obsolete_replays"] == 1

    db = SessionLocal()
    replays = db.query(BattleReplayNormalized).all()
    logs = db.query(PlayerMatchupLog).all()
    stats = db.query(PlayerMatchupStat).all()
    assert len(replays) == 1
    assert replays[0].battle_id == 102
    assert len(logs) == 2
    assert len(stats) == 1
    assert stats[0].total_battles == 2
    assert stats[0].player_low_wins == 1
    assert stats[0].player_high_wins == 1
    db.close()


def test_backfill_treats_swapped_roles_as_same_pair(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s2",
        captured_at=now - timedelta(minutes=2),
        battle_id=201,
        attacker_user_id=11,
        attacker_name="P1",
        defender_user_id=22,
        defender_name="P2",
        outcome_type="Attacker Won",
    )
    _insert_replay(
        db,
        session_id="s2",
        captured_at=now - timedelta(minutes=1),
        battle_id=202,
        attacker_user_id=22,
        attacker_name="P2",
        defender_user_id=11,
        defender_name="P1",
        outcome_type="Defender Won",
    )
    db.commit()
    db.close()

    repo.backfill_matchup_history_and_prune()

    db = SessionLocal()
    pair_logs = (
        db.query(PlayerMatchupLog)
        .filter(
            PlayerMatchupLog.player_low_user_id == 11,
            PlayerMatchupLog.player_high_user_id == 22,
        )
        .all()
    )
    assert len(pair_logs) == 2
    assert db.query(BattleReplayNormalized).count() == 1
    db.close()


def test_duplicate_battle_id_does_not_duplicate_log(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s3",
        captured_at=now - timedelta(minutes=2),
        battle_id=301,
        attacker_user_id=31,
        attacker_name="A",
        defender_user_id=41,
        defender_name="B",
        outcome_type="Attacker Won",
    )
    _insert_replay(
        db,
        session_id="s3",
        captured_at=now - timedelta(minutes=1),
        battle_id=301,
        attacker_user_id=31,
        attacker_name="A",
        defender_user_id=41,
        defender_name="B",
        outcome_type="Attacker Won",
    )
    db.commit()
    db.close()

    metrics = repo.backfill_matchup_history_and_prune()
    assert metrics["inserted_logs"] == 1

    db = SessionLocal()
    assert db.query(PlayerMatchupLog).count() == 1
    stat = db.query(PlayerMatchupStat).first()
    assert stat is not None
    assert stat.total_battles == 1
    db.close()


def test_delete_event_updates_matchup_stats(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s4",
        captured_at=now - timedelta(minutes=2),
        battle_id=401,
        attacker_user_id=51,
        attacker_name="A1",
        defender_user_id=61,
        defender_name="B1",
        outcome_type="Attacker Won",
    )
    _insert_replay(
        db,
        session_id="s4",
        captured_at=now - timedelta(minutes=1),
        battle_id=402,
        attacker_user_id=51,
        attacker_name="A1",
        defender_user_id=61,
        defender_name="B1",
        outcome_type="Defender Won",
    )
    db.commit()
    db.close()

    repo.backfill_matchup_history_and_prune()

    db = SessionLocal()
    replay = db.query(BattleReplayNormalized).first()
    assert replay is not None
    event_id = int(replay.api_flow_event_id)
    db.close()

    assert repo.delete_event(event_id) == 1

    db = SessionLocal()
    assert db.query(BattleReplayNormalized).count() == 0
    assert db.query(PlayerMatchupLog).count() == 1
    stat = db.query(PlayerMatchupStat).first()
    assert stat is not None
    assert stat.total_battles == 1
    db.close()


def test_clear_battle_replays_clears_matchup_tables(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s5",
        captured_at=now,
        battle_id=501,
        attacker_user_id=71,
        attacker_name="A2",
        defender_user_id=81,
        defender_name="B2",
        outcome_type="Attacker Won",
    )
    db.commit()
    db.close()

    repo.backfill_matchup_history_and_prune()
    assert repo.clear_battle_replays() == 1

    db = SessionLocal()
    assert db.query(BattleReplayNormalized).count() == 0
    assert db.query(PlayerMatchupLog).count() == 0
    assert db.query(PlayerMatchupStat).count() == 0
    db.close()


def test_battle_detail_includes_matchup_summary_and_recent_log(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _insert_replay(
        db,
        session_id="s6",
        captured_at=now - timedelta(minutes=2),
        battle_id=601,
        attacker_user_id=91,
        attacker_name="AAA",
        defender_user_id=92,
        defender_name="BBB",
        outcome_type="Attacker Won",
    )
    latest, _ = _insert_replay(
        db,
        session_id="s6",
        captured_at=now - timedelta(minutes=1),
        battle_id=602,
        attacker_user_id=91,
        attacker_name="AAA",
        defender_user_id=92,
        defender_name="BBB",
        outcome_type="Defender Won",
    )
    db.commit()
    battle_replay_id = int(latest.id)
    db.close()

    repo.backfill_matchup_history_and_prune()

    detail = repo.get_battle_replay_detail(battle_replay_id)
    assert detail is not None
    summary = detail.get("matchup_summary") or {}
    recent = detail.get("matchup_recent_log") or []
    assert summary.get("total_battles") == 2
    assert summary.get("player_low_user_id") == 91
    assert summary.get("player_high_user_id") == 92
    assert len(recent) >= 1
