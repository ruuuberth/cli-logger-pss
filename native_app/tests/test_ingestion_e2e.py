from __future__ import annotations

import html
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.services.api_flow_storage as storage_module
from app.models.database import Base
from app.models.pss_models import (
    ApiFlowEvent,
    BattleReplayCharacter,
    BattleReplayCommand,
    BattleReplayNormalized,
    BattleReplayRoom,
    BattleReplayShip,
    PlayerMatchupLog,
    PlayerMatchupStat,
)


def _build_repo(monkeypatch):
    test_engine = create_engine("sqlite:///:memory:")
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_engine
    )
    Base.metadata.create_all(test_engine)
    monkeypatch.setattr(storage_module, "SessionLocal", TestingSessionLocal)
    monkeypatch.setattr(storage_module, "engine", test_engine)
    return storage_module.ApiFlowRepository(), TestingSessionLocal


def _battle_xml(
    battle_id: int,
    attacker_id: int,
    attacker_name: str,
    defender_id: int,
    defender_name: str,
    outcome: str = "Attacker Won",
) -> str:
    """Build GetBattle3 response XML with HTML-escaped nested payloads.

    Mirrors the shape the mitmproxy addon emits in ``response_body_preview``:
    nested XML (users, ships, rooms, characters, commands) lives inside
    attribute values and is HTML-escaped.
    """
    attacker_user = html.escape(
        f'<User Id="{attacker_id}" Name="{attacker_name}" Trophy="5000" />',
        quote=True,
    )
    defender_user = html.escape(
        f'<User Id="{defender_id}" Name="{defender_name}" Trophy="4800" />',
        quote=True,
    )
    attacker_ship = html.escape(
        '<Ship ShipId="100" ShipDesignId="200" ShipName="Attacker Ship" '
        'ShipLevel="12" PowerScore="1100" Hp="40.5" ShipStatus="Online">'
        '<Rooms><Room RoomId="501" RoomDesignId="700" ShipId="100" '
        'Row="20" Column="40" RoomStatus="Normal"/></Rooms>'
        '<Characters><Character CharacterId="9001" ShipId="100" '
        'CharacterDesignId="300" CharacterName="Crew A" Level="40" Xp="1000"/></Characters>'
        "</Ship>",
        quote=True,
    )
    defender_ship = html.escape(
        '<Ship ShipId="101" ShipDesignId="201" ShipName="Defender Ship" '
        'ShipLevel="11" PowerScore="1000" Hp="35.0" ShipStatus="Online">'
        '<Rooms><Room RoomId="502" RoomDesignId="701" ShipId="101" '
        'Row="10" Column="20" RoomStatus="Normal"/></Rooms>'
        '<Characters><Character CharacterId="9002" ShipId="101" '
        'CharacterDesignId="301" CharacterName="Crew B" Level="35" Xp="800"/></Characters>'
        "</Ship>",
        quote=True,
    )
    commands = html.escape(
        '<UserCommands><Commands><Command UserId="10" ShipId="100" RoomId="501" '
        'CharacterId="9001"/></Commands></UserCommands>',
        quote=True,
    )
    return (
        "<BattleService><GetBattle><Battle "
        f'BattleId="{battle_id}" '
        f'OutcomeType="{outcome}" '
        f'AttackingUserXml="{attacker_user}" '
        f'DefendingUserXml="{defender_user}" '
        f'AttackingShipXml="{attacker_ship}" '
        f'DefendingShipXml="{defender_ship}" '
        f'Commands="{commands}"'
        "/></GetBattle></BattleService>"
    )


def _make_event(
    battle_id: int,
    captured_at: datetime,
    attacker_id: int = 10,
    attacker_name: str = "Alice",
    defender_id: int = 20,
    defender_name: str = "Bob",
    outcome: str = "Attacker Won",
) -> dict:
    return {
        "session_id": f"s{battle_id}",
        "captured_at": captured_at,
        "direction": "response",
        "method": "POST",
        "host": "api.pixelstarships.com",
        "port": 443,
        "path": "/BattleService/GetBattle3",
        "query": f"?battleId={battle_id}",
        "url_full": f"https://api.pixelstarships.com/BattleService/GetBattle3?battleId={battle_id}",
        "status_code": 200,
        "response_body_preview": _battle_xml(
            battle_id, attacker_id, attacker_name, defender_id, defender_name, outcome
        ),
    }


def test_happy_path_keep_n_retains_newest_battles(monkeypatch) -> None:
    """keep=3 over 4 distinct battles: 3 newest replays retained, oldest pruned,
    all 4 matchup logs kept, stats recompute to 4 battles, child rows exist."""
    repo, SessionLocal = _build_repo(monkeypatch)
    monkeypatch.setattr(
        storage_module.settings, "API_FLOW_REPLAYS_PER_PAIR", 3, raising=False
    )

    now = datetime.now(UTC)
    events = [
        _make_event(301, now - timedelta(minutes=40)),
        _make_event(302, now - timedelta(minutes=30)),
        _make_event(303, now - timedelta(minutes=20)),
        _make_event(304, now - timedelta(minutes=10)),
    ]

    saved = repo.save_events(events)
    assert saved == 4

    db = SessionLocal()
    try:
        # 3 newest distinct battles survive pruning; the oldest (301) is gone.
        replays = (
            db.query(BattleReplayNormalized)
            .order_by(BattleReplayNormalized.battle_id)
            .all()
        )
        assert [r.battle_id for r in replays] == [302, 303, 304]
        assert db.query(ApiFlowEvent).count() == 3

        # Matchup logs keep full history (one per distinct battle).
        logs = db.query(PlayerMatchupLog).all()
        assert len(logs) == 4
        assert {log.battle_id for log in logs} == {301, 302, 303, 304}

        # Stats recompute over all logs.
        stats = db.query(PlayerMatchupStat).all()
        assert len(stats) == 1
        assert stats[0].total_battles == 4

        # Child rows exist for the surviving replays (3 replays x 2 ships).
        assert db.query(BattleReplayShip).count() == 6
        assert db.query(BattleReplayRoom).count() == 6
        assert db.query(BattleReplayCharacter).count() == 6
        assert db.query(BattleReplayCommand).count() == 3
    finally:
        db.close()


def test_duplicate_capture_dedupes_battles_and_logs(monkeypatch) -> None:
    """Same battleId captured twice plus two more: 3 distinct replay slots,
    no duplicate matchup log, battles_analyzed == 3."""
    repo, SessionLocal = _build_repo(monkeypatch)
    monkeypatch.setattr(
        storage_module.settings, "API_FLOW_REPLAYS_PER_PAIR", 3, raising=False
    )

    now = datetime.now(UTC)
    events = [
        _make_event(101, now - timedelta(minutes=40)),
        _make_event(101, now - timedelta(minutes=30)),  # re-capture of same battle
        _make_event(102, now - timedelta(minutes=20)),
        _make_event(103, now - timedelta(minutes=10)),
    ]

    saved = repo.save_events(events)
    assert saved == 4

    db = SessionLocal()
    try:
        replays = (
            db.query(BattleReplayNormalized)
            .order_by(BattleReplayNormalized.battle_id)
            .all()
        )
        assert [r.battle_id for r in replays] == [101, 102, 103]
        assert len(replays) == 3  # duplicate never wastes a retention slot

        logs = db.query(PlayerMatchupLog).all()
        assert len(logs) == 3  # no duplicate log for the repeated battle_id
        assert {log.battle_id for log in logs} == {101, 102, 103}

        stats = db.query(PlayerMatchupStat).all()
        assert len(stats) == 1
        assert stats[0].total_battles == 3
    finally:
        db.close()


def test_html_escaped_xml_cleaning_survives_ingestion(monkeypatch) -> None:
    """Raw preview keeps escaped form; cleaned output parses as nested JSON;
    normalized row derives from it."""
    repo, SessionLocal = _build_repo(monkeypatch)

    now = datetime.now(UTC)
    event = _make_event(501, now - timedelta(minutes=5))

    saved = repo.save_events([event])
    assert saved == 1

    db = SessionLocal()
    try:
        api_flow_event = db.query(ApiFlowEvent).first()
        assert api_flow_event is not None

        # Raw preview keeps the escaped form.
        assert "&lt;" in api_flow_event.response_body_preview
        assert "&quot;" in api_flow_event.response_body_preview

        # Cleaned output parses as nested JSON.
        cleaned = json.loads(api_flow_event.response_body_cleaned)
        battle_node = cleaned["children"][0]["children"][0]
        assert battle_node["tag"] == "Battle"
        assert battle_node["attributes"]["BattleId"] == "501"
        # Nested payloads are parsed as dicts, not left as escaped strings.
        assert isinstance(battle_node["attributes"]["AttackingUserXml"], dict)
        assert isinstance(battle_node["attributes"]["AttackingShipXml"], dict)

        # Normalized row derives from the cleaned payload.
        replay = db.query(BattleReplayNormalized).first()
        assert replay is not None
        assert replay.battle_id == 501
        assert replay.attacker_name == "Alice"
        assert replay.defender_name == "Bob"
        assert replay.outcome_type == "Attacker Won"

        assert db.query(PlayerMatchupLog).count() == 1
        assert db.query(PlayerMatchupStat).first().total_battles == 1
    finally:
        db.close()


def test_non_whitelisted_path_and_empty_batch_persist_nothing(monkeypatch) -> None:
    """/UserService/SearchUsers persists nothing; an empty batch returns zero."""
    repo, SessionLocal = _build_repo(monkeypatch)

    now = datetime.now(UTC)
    non_whitelisted = dict(
        session_id="sx",
        captured_at=now,
        direction="response",
        method="GET",
        host="api.pixelstarships.com",
        port=443,
        path="/UserService/SearchUsers",
        query="?name=x",
        url_full="https://api.pixelstarships.com/UserService/SearchUsers?name=x",
        status_code=200,
        response_body_preview="<UserService><SearchUsers /></UserService>",
    )

    assert repo.save_events([]) == 0
    assert repo.save_events([non_whitelisted]) == 0

    db = SessionLocal()
    try:
        assert db.query(ApiFlowEvent).count() == 0
        assert db.query(BattleReplayNormalized).count() == 0
        assert db.query(PlayerMatchupLog).count() == 0
        assert db.query(PlayerMatchupStat).count() == 0
    finally:
        db.close()
