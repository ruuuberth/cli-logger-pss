"""Tests for the H2H per-player fleet breakdown (ships/rooms/crew attribution)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.pss_models import (
    ApiFlowEvent,
    BattleReplayCharacter,
    BattleReplayNormalized,
    BattleReplayRoom,
    BattleReplayShip,
    CrewDesign,
    RoomDesign,
    ShipDesign,
)
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
    battle_id: int,
    attacker_user_id: int,
    defender_user_id: int,
    captured_at: datetime,
    outcome_type: str = "Attacker Won",
):
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
        attacker_user_id=attacker_user_id,
        attacker_name=f"P{attacker_user_id}",
        defender_user_id=defender_user_id,
        defender_name=f"P{defender_user_id}",
        outcome_type=outcome_type,
    )
    db.add(replay)
    db.flush()
    return replay


def _insert_ship(db, replay, *, side: str, ship_id: int, design_id: int, level: int | None, power: int | None):
    db.add(BattleReplayShip(
        battle_replay_id=replay.id,
        side=side,
        ship_id=ship_id,
        ship_design_id=design_id,
        ship_name=f"Ship{design_id}",
        ship_level=level,
        power_score=power,
    ))


def _insert_room(db, replay, *, side: str, room_id: int, design_id: int):
    db.add(BattleReplayRoom(
        battle_replay_id=replay.id,
        side=side,
        room_id=room_id,
        room_design_id=design_id,
    ))


def _insert_character(db, replay, *, side: str, character_id: int, design_id: int, level: int):
    db.add(BattleReplayCharacter(
        battle_replay_id=replay.id,
        side=side,
        character_id=character_id,
        character_design_id=design_id,
        character_name=f"Crew{design_id}",
        level=level,
    ))


def _seed_designs(db):
    db.add(ShipDesign(ship_design_id=500, name="Battleship EN", name_es="Acorazado"))
    db.add(RoomDesign(room_design_id=600, name="Shield EN", name_es="Escudo"))
    db.add(CrewDesign(crew_design_id=700, name="Pilot EN", name_es="Piloto"))


def test_fleet_breakdown_attributes_sides_per_battle(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    _seed_designs(db)

    # Battle 1: 10 attacks 20 -> attacker side belongs to player 10
    r1 = _insert_replay(db, battle_id=101, attacker_user_id=10, defender_user_id=20,
                         captured_at=now - timedelta(minutes=2))
    _insert_ship(db, r1, side="attacker", ship_id=11, design_id=500, level=8, power=4200)
    _insert_ship(db, r1, side="defender", ship_id=21, design_id=500, level=6, power=3900)
    _insert_room(db, r1, side="attacker", room_id=111, design_id=600)
    _insert_room(db, r1, side="defender", room_id=211, design_id=600)
    _insert_character(db, r1, side="attacker", character_id=112, design_id=700, level=12)
    _insert_character(db, r1, side="defender", character_id=212, design_id=700, level=9)

    # Battle 2: 20 attacks 10 -> attacker side NOW belongs to player 20
    r2 = _insert_replay(db, battle_id=102, attacker_user_id=20, defender_user_id=10,
                         captured_at=now - timedelta(minutes=1), outcome_type="Defender Won")
    _insert_ship(db, r2, side="attacker", ship_id=21, design_id=500, level=7, power=4100)
    _insert_ship(db, r2, side="defender", ship_id=11, design_id=500, level=9, power=4300)
    _insert_room(db, r2, side="defender", room_id=111, design_id=600)
    _insert_character(db, r2, side="attacker", character_id=212, design_id=700, level=10)

    db.commit()
    db.close()

    breakdown = repo.get_h2h_fleet_breakdown(low_user_id=10, high_user_id=20)
    assert breakdown is not None
    assert breakdown["battles_analyzed"] == 2

    low = breakdown["player_low"]
    high = breakdown["player_high"]
    assert low["user_id"] == 10
    assert high["user_id"] == 20

    # Player 10 fielded ship 11 twice (attacker in b1, defender in b2)
    low_ships = {s["id"]: s for s in low["ships"]}
    assert low_ships[11]["battles"] == 2
    # avg of levels 8 and 9
    assert low_ships[11]["avg_level"] == 8.5
    assert low_ships[11]["avg_power_score"] == 4250.0
    assert low_ships[11]["ship_design_name"] == "Acorazado"  # ES preferred

    # Player 20 fielded ship 21 twice
    high_ships = {s["id"]: s for s in high["ships"]}
    assert high_ships[21]["battles"] == 2
    assert high_ships[21]["avg_level"] == 6.5

    # Rooms: player 10 room 111 in b1(attacker)+b2(defender) = 2; player 20 room 211 only b1 = 1
    low_rooms = {r["id"]: r for r in low["rooms"]}
    high_rooms = {r["id"]: r for r in high["rooms"]}
    assert low_rooms[111]["battles"] == 2
    assert high_rooms[211]["battles"] == 1
    assert low_rooms[111]["room_design_name"] == "Escudo"

    # Crew: player 10 has crew 112 (b1) + nothing in b2; player 20 has crew 212 twice
    low_crew = {c["id"]: c for c in low["crew"]}
    high_crew = {c["id"]: c for c in high["crew"]}
    assert low_crew[112]["battles"] == 1
    assert high_crew[212]["battles"] == 2
    assert high_crew[212]["avg_level"] == 9.5
    assert low_crew[112]["character_design_name"] == "Piloto"


def test_fleet_breakdown_respects_date_and_outcome_filters(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    r1 = _insert_replay(db, battle_id=201, attacker_user_id=10, defender_user_id=20,
                         captured_at=now - timedelta(days=10), outcome_type="Attacker Won")
    _insert_ship(db, r1, side="attacker", ship_id=11, design_id=500, level=5, power=1000)
    r2 = _insert_replay(db, battle_id=202, attacker_user_id=10, defender_user_id=20,
                         captured_at=now - timedelta(days=1), outcome_type="Defender Won")
    _insert_ship(db, r2, side="attacker", ship_id=11, design_id=500, level=6, power=1100)
    db.commit()
    db.close()

    # No filter: both battles
    all_b = repo.get_h2h_fleet_breakdown(10, 20)
    assert all_b["battles_analyzed"] == 2

    # Date filter: only the recent battle
    recent_b = repo.get_h2h_fleet_breakdown(10, 20, date_from=now - timedelta(days=2))
    assert recent_b["battles_analyzed"] == 1
    ships = {s["id"]: s for s in recent_b["player_low"]["ships"]}
    assert ships[11]["avg_level"] == 6

    # Outcome filter
    won_b = repo.get_h2h_fleet_breakdown(10, 20, outcome="Defender Won")
    assert won_b["battles_analyzed"] == 1


def test_fleet_breakdown_skips_missing_ship_metrics(monkeypatch) -> None:
    """A fallback ship row (no XML) must not drag averages toward zero."""
    repo, SessionLocal = _build_repo(monkeypatch)
    now = datetime.now(timezone.utc)

    db = SessionLocal()
    # Complete capture: level 8, power 4200
    r1 = _insert_replay(db, battle_id=401, attacker_user_id=10, defender_user_id=20,
                         captured_at=now - timedelta(minutes=2))
    _insert_ship(db, r1, side="attacker", ship_id=11, design_id=500, level=8, power=4200)
    # Fallback-style capture: same ship, level/power unset (missing XML)
    r2 = _insert_replay(db, battle_id=402, attacker_user_id=10, defender_user_id=20,
                         captured_at=now - timedelta(minutes=1))
    _insert_ship(db, r2, side="attacker", ship_id=11, design_id=500, level=None, power=None)
    db.commit()
    db.close()

    breakdown = repo.get_h2h_fleet_breakdown(10, 20)
    ships = {s["id"]: s for s in breakdown["player_low"]["ships"]}
    # Averages over observed values only: 8 and 4200, not dragged to 4/2100
    assert ships[11]["battles"] == 2
    assert ships[11]["avg_level"] == 8
    assert ships[11]["avg_power_score"] == 4200.0


def test_fleet_breakdown_returns_none_for_unknown_pair(monkeypatch) -> None:
    repo, SessionLocal = _build_repo(monkeypatch)
    db = SessionLocal()
    _insert_replay(db, battle_id=301, attacker_user_id=10, defender_user_id=20,
                   captured_at=datetime.now(timezone.utc))
    db.commit()
    db.close()

    assert repo.get_h2h_fleet_breakdown(999, 888) is None
