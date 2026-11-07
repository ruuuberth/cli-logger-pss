"""H2H (head-to-head) query functions.

Extracted from ApiFlowRepository (api_flow_storage.py). The 6 public
functions here are the entire read-side of the H2H feature: summary
metrics, battle list, trends, fleet breakdown, and pair search. They
share small helpers that also live in this module.

ApiFlowRepository keeps thin delegating methods so existing callers
(ApiFlowListService) and tests keep working unchanged.

shortcut: _as_int is duplicated from api_flow_storage (7-line pure
coercion); importing it back would create a storage<->h2h import cycle.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

from sqlalchemy import String, and_, cast, or_
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

from app.models.database import SessionLocal
from app.models.pss_models import (
    BattleReplayCharacter,
    BattleReplayNormalized,
    BattleReplayRoom,
    BattleReplayShip,
    CrewDesign,
    PlayerMatchupLog,
    PlayerMatchupStat,
    RoomDesign,
    ShipDesign,
)
from app.services.text_cleaning import normalize_text as _normalize_text

logger = logging.getLogger(__name__)


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _translate_design_name(
    design_id: int | None,
    map_es: dict[int, str] | None,
    map_en: dict[int, str] | None,
    raw_name: str | None,
) -> str:
    if design_id is not None:
        if map_es:
            value = map_es.get(int(design_id))
            if value and str(value).strip():
                return _normalize_text(value) or str(value).strip()
        if map_en:
            value = map_en.get(int(design_id))
            if value and str(value).strip():
                return _normalize_text(value) or str(value).strip()
    if raw_name and str(raw_name).strip():
        return _normalize_text(raw_name) or str(raw_name).strip()
    if design_id is not None:
        return str(design_id)
    return "Sin traduccion"


def _load_design_maps(
    db: Any,
    model: Any,
    design_id_col: Any,
    design_ids: set[int],
) -> tuple[dict[int, str], dict[int, str]]:
    """Load (es, en) design-name maps for the given design ids."""
    map_es: dict[int, str] = {}
    map_en: dict[int, str] = {}
    if not design_ids:
        return map_es, map_en
    try:
        rows = (
            db.query(design_id_col, model.name, model.name_es)
            .filter(design_id_col.in_(sorted(design_ids)))
            .all()
        )
    except SQLAlchemyOperationalError:
        return map_es, map_en
    for design_id, name, name_es in rows:
        if design_id is None:
            continue
        if name:
            map_en[int(design_id)] = str(name)
        if name_es:
            map_es[int(design_id)] = str(name_es)
    return map_es, map_en


def get_h2h_summary(
    low_user_id: int,
    high_user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outcome: str | None = None,
) -> dict[str, Any] | None:
    """Get H2H summary metrics for a player pair"""
    db = SessionLocal()
    try:
        pair_filters = [
            and_(
                PlayerMatchupLog.player_low_user_id == low_user_id,
                PlayerMatchupLog.player_high_user_id == high_user_id,
            )
        ]
        query = db.query(PlayerMatchupLog).filter(or_(*pair_filters))

        if date_from is not None:
            query = query.filter(PlayerMatchupLog.captured_at >= date_from)
        if date_to is not None:
            query = query.filter(PlayerMatchupLog.captured_at <= date_to)
        if outcome:
            query = query.filter(PlayerMatchupLog.outcome_type == outcome)

        logs = query.order_by(
            PlayerMatchupLog.captured_at.desc(), PlayerMatchupLog.id.desc()
        ).all()

        if not logs:
            return None

        low_wins = 0
        high_wins = 0
        unknown_results = 0

        first_date = None
        last_date = None

        for log in logs:
            winner_id = _as_int(log.winner_user_id)
            if winner_id == low_user_id:
                low_wins += 1
            elif winner_id == high_user_id:
                high_wins += 1
            else:
                unknown_results += 1

            if log.captured_at:
                if first_date is None or log.captured_at < first_date:
                    first_date = log.captured_at
                if last_date is None or log.captured_at > last_date:
                    last_date = log.captured_at

        latest_replay = (
            db.query(BattleReplayNormalized)
            .filter(
                or_(
                    and_(
                        BattleReplayNormalized.attacker_user_id == low_user_id,
                        BattleReplayNormalized.defender_user_id == high_user_id,
                    ),
                    and_(
                        BattleReplayNormalized.attacker_user_id == high_user_id,
                        BattleReplayNormalized.defender_user_id == low_user_id,
                    ),
                )
            )
            .order_by(
                BattleReplayNormalized.captured_at.desc(),
                BattleReplayNormalized.id.desc(),
            )
            .first()
        )

        low_name = None
        high_name = None
        if latest_replay:
            if _as_int(latest_replay.attacker_user_id) == low_user_id:
                low_name = latest_replay.attacker_name
                high_name = latest_replay.defender_name
            else:
                low_name = latest_replay.defender_name
                high_name = latest_replay.attacker_name

        return {
            "player_low_user_id": low_user_id,
            "player_high_user_id": high_user_id,
            "player_low_name": low_name,
            "player_high_name": high_name,
            "total_battles": len(logs),
            "player_low_wins": low_wins,
            "player_high_wins": high_wins,
            "unknown_results": unknown_results,
            "first_battle_date": first_date,
            "last_battle_date": last_date,
        }
    finally:
        db.close()


def get_h2h_battles(
    low_user_id: int,
    high_user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outcome: str | None = None,
    limit: int = 1000,
) -> list[dict[str, Any]]:
    """Get detailed battles for a player pair"""
    db = SessionLocal()
    try:
        query = db.query(BattleReplayNormalized).filter(
            or_(
                and_(
                    BattleReplayNormalized.attacker_user_id == low_user_id,
                    BattleReplayNormalized.defender_user_id == high_user_id,
                ),
                and_(
                    BattleReplayNormalized.attacker_user_id == high_user_id,
                    BattleReplayNormalized.defender_user_id == low_user_id,
                ),
            )
        )

        if date_from is not None:
            query = query.filter(BattleReplayNormalized.captured_at >= date_from)
        if date_to is not None:
            query = query.filter(BattleReplayNormalized.captured_at <= date_to)
        if outcome:
            query = query.filter(BattleReplayNormalized.outcome_type == outcome)

        battles = (
            query.order_by(
                BattleReplayNormalized.captured_at.desc(),
                BattleReplayNormalized.id.desc(),
            )
            .limit(limit)
            .all()
        )

        result = []
        for b in battles:
            is_low_attacker = _as_int(b.attacker_user_id) == low_user_id
            result.append(
                {
                    "captured_at": b.captured_at,
                    "battle_id": b.battle_id,
                    "attacker_name": b.attacker_name,
                    "defender_name": b.defender_name,
                    "outcome": b.outcome_type,
                    "attacker_trophy_delta": b.win_trophy_result
                    if is_low_attacker
                    else b.lose_trophy_result,
                    "defender_trophy_delta": b.lose_trophy_result
                    if is_low_attacker
                    else b.win_trophy_result,
                    "loot_minerals": f"M {b.win_minerals_result or 0}/{b.lose_minerals_result or 0}",
                    "loot_gas": f"G {b.win_gas_result or 0}/{b.lose_gas_result or 0}",
                }
            )
        return result
    finally:
        db.close()


def get_h2h_trends(
    low_user_id: int,
    high_user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outcome: str | None = None,
    bucket: str = "day",
) -> list[dict[str, Any]]:
    """Get time-series trend data for H2H (bucketed by day/week)"""
    db = SessionLocal()
    try:
        query = db.query(PlayerMatchupLog).filter(
            or_(
                and_(
                    PlayerMatchupLog.player_low_user_id == low_user_id,
                    PlayerMatchupLog.player_high_user_id == high_user_id,
                ),
                and_(
                    PlayerMatchupLog.player_low_user_id == high_user_id,
                    PlayerMatchupLog.player_high_user_id == low_user_id,
                ),
            )
        )

        if date_from is not None:
            query = query.filter(PlayerMatchupLog.captured_at >= date_from)
        if date_to is not None:
            query = query.filter(PlayerMatchupLog.captured_at <= date_to)
        if outcome:
            query = query.filter(PlayerMatchupLog.outcome_type == outcome)

        logs = query.order_by(PlayerMatchupLog.captured_at.asc()).all()

        if not logs:
            return []

        from collections import defaultdict

        buckets = defaultdict(
            lambda: {
                "battle_count": 0,
                "player_low_wins": 0,
                "player_high_wins": 0,
                "player_low_trophies": [],
                "player_high_trophies": [],
            }
        )

        for log in logs:
            dt = log.captured_at
            if dt is None:
                continue

            if bucket == "week":
                period = dt.strftime("%Y-W%U")
            else:
                period = dt.strftime("%Y-%m-%d")

            buckets[period]["battle_count"] += 1

            winner_id = _as_int(log.winner_user_id)
            if winner_id == low_user_id:
                buckets[period]["player_low_wins"] += 1
            elif winner_id == high_user_id:
                buckets[period]["player_high_wins"] += 1

            replay = (
                db.query(BattleReplayNormalized)
                .filter(BattleReplayNormalized.battle_id == log.battle_id)
                .first()
            )
            if replay:
                if _as_int(replay.attacker_user_id) == low_user_id:
                    if replay.attacker_trophy is not None:
                        buckets[period]["player_low_trophies"].append(
                            replay.attacker_trophy
                        )
                    if replay.defender_trophy is not None:
                        buckets[period]["player_high_trophies"].append(
                            replay.defender_trophy
                        )
                else:
                    if replay.defender_trophy is not None:
                        buckets[period]["player_low_trophies"].append(
                            replay.defender_trophy
                        )
                    if replay.attacker_trophy is not None:
                        buckets[period]["player_high_trophies"].append(
                            replay.attacker_trophy
                        )

        trends = []
        for period in sorted(buckets.keys()):
            data = buckets[period]
            low_trophies = data["player_low_trophies"]
            high_trophies = data["player_high_trophies"]
            trends.append(
                {
                    "period": period,
                    "battle_count": data["battle_count"],
                    "player_low_wins": data["player_low_wins"],
                    "player_high_wins": data["player_high_wins"],
                    "player_low_avg_trophies": sum(low_trophies) // len(low_trophies)
                    if low_trophies
                    else 0,
                    "player_high_avg_trophies": sum(high_trophies) // len(high_trophies)
                    if high_trophies
                    else 0,
                }
            )

        return trends
    finally:
        db.close()


def get_h2h_fleet_breakdown(
    low_user_id: int,
    high_user_id: int,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    outcome: str | None = None,
    limit: int = 1000,
) -> dict[str, Any] | None:
    """Per-player fleet breakdown (ships/rooms/crew) for an H2H pair.

    Aggregates the normalized replay data for battles between the pair,
    attributing each side to the player who fielded it (attacker/defender).
    Returns None when the pair has no battles.

    Retention note: captures prune normalized replays per pair, keeping
    the newest `API_FLOW_REPLAYS_PER_PAIR` battles (default 1 — legacy
    behavior). With retention > 1 this breakdown reports real usage
    counts across the retained history.
    """
    db = SessionLocal()
    try:
        replays = db.query(BattleReplayNormalized).filter(
            or_(
                and_(
                    BattleReplayNormalized.attacker_user_id == low_user_id,
                    BattleReplayNormalized.defender_user_id == high_user_id,
                ),
                and_(
                    BattleReplayNormalized.attacker_user_id == high_user_id,
                    BattleReplayNormalized.defender_user_id == low_user_id,
                ),
            )
        )
        if date_from is not None:
            replays = replays.filter(BattleReplayNormalized.captured_at >= date_from)
        if date_to is not None:
            replays = replays.filter(BattleReplayNormalized.captured_at <= date_to)
        if outcome:
            replays = replays.filter(BattleReplayNormalized.outcome_type == outcome)

        replays = (
            replays.order_by(
                BattleReplayNormalized.captured_at.desc(),
                BattleReplayNormalized.id.desc(),
            )
            .limit(limit)
            .all()
        )
        if not replays:
            return None

        replay_ids = [r.id for r in replays]
        battle_ids = [r.battle_id for r in replays if r.battle_id is not None]

        ships = (
            db.query(BattleReplayShip)
            .filter(BattleReplayShip.battle_replay_id.in_(replay_ids))
            .all()
        )
        rooms = (
            db.query(BattleReplayRoom)
            .filter(BattleReplayRoom.battle_replay_id.in_(replay_ids))
            .all()
        )
        characters = (
            db.query(BattleReplayCharacter)
            .filter(BattleReplayCharacter.battle_replay_id.in_(replay_ids))
            .all()
        )

        # Attribute each replay row to the player who fielded that side:
        # a row with side="attacker" belongs to the replay's attacker, etc.
        side_owner: dict[tuple[int, str], int] = {}
        for r in replays:
            attacker_id = _as_int(r.attacker_user_id)
            defender_id = _as_int(r.defender_user_id)
            if attacker_id is not None:
                side_owner[(r.id, "attacker")] = attacker_id
            if defender_id is not None:
                side_owner[(r.id, "defender")] = defender_id

        ship_map_es, ship_map_en = _load_design_maps(
            db,
            ShipDesign,
            ShipDesign.ship_design_id,
            {int(s.ship_design_id) for s in ships if s.ship_design_id is not None},
        )
        room_map_es, room_map_en = _load_design_maps(
            db,
            RoomDesign,
            RoomDesign.room_design_id,
            {int(r.room_design_id) for r in rooms if r.room_design_id is not None},
        )
        crew_map_es, crew_map_en = _load_design_maps(
            db,
            CrewDesign,
            CrewDesign.crew_design_id,
            {
                int(c.character_design_id)
                for c in characters
                if c.character_design_id is not None
            },
        )

        def _owner_key_for(
            row_side: str, replay_row: BattleReplayNormalized
        ) -> str | None:
            """Return 'player_low'/'player_high' for the fielding player, or None if unknown."""
            owner_id = side_owner.get((replay_row.id, row_side))
            if owner_id == low_user_id:
                return "player_low"
            if owner_id == high_user_id:
                return "player_high"
            return None

        players = {
            "player_low": _init_breakdown_player(low_user_id),
            "player_high": _init_breakdown_player(high_user_id),
        }
        # Map replay_id -> replay row for owner lookups
        replays_by_id = {r.id: r for r in replays}

        for s in ships:
            replay_row = replays_by_id.get(s.battle_replay_id)
            if replay_row is None:
                continue
            key = _owner_key_for(s.side, replay_row)
            if key is None:
                continue
            if s.ship_id is None:
                # Fallback ship row (missing XML, no ShipId): no fleet info.
                continue
            bucket = players[key]["ships"][s.ship_id]
            bucket["battles"] += 1
            if s.ship_name:
                bucket["ship_name"] = _normalize_text(s.ship_name) or bucket.get(
                    "ship_name"
                )
            if s.ship_design_id is not None:
                bucket["ship_design_id"] = int(s.ship_design_id)
                bucket["ship_design_name"] = _translate_design_name(
                    s.ship_design_id, ship_map_es, ship_map_en, s.ship_name
                )
            ship_level = _as_int(s.ship_level)
            if ship_level is not None:
                bucket["levels"].append(ship_level)
            ship_power = _as_int(s.power_score)
            if ship_power is not None:
                bucket["power_scores"].append(ship_power)

        for room in rooms:
            replay_row = replays_by_id.get(room.battle_replay_id)
            if replay_row is None:
                continue
            key = _owner_key_for(room.side, replay_row)
            if key is None:
                continue
            if room.room_id is None:
                # Unidentified room (partial capture): cannot be counted
                # reliably; merging would fabricate a single room with
                # inflated usage counts and overwritten design names.
                continue
            bucket = players[key]["rooms"][room.room_id]
            bucket["battles"] += 1
            if room.room_design_id is not None:
                bucket["room_design_id"] = int(room.room_design_id)
                bucket["room_design_name"] = _translate_design_name(
                    room.room_design_id, room_map_es, room_map_en, None
                )

        for c in characters:
            replay_row = replays_by_id.get(c.battle_replay_id)
            if replay_row is None:
                continue
            key = _owner_key_for(c.side, replay_row)
            if key is None:
                continue
            if c.character_id is None:
                # Unidentified crew member (partial capture).
                continue
            bucket = players[key]["crew"][c.character_id]
            bucket["battles"] += 1
            if c.character_name:
                bucket["character_name"] = _normalize_text(
                    c.character_name
                ) or bucket.get("character_name")
            if c.character_design_id is not None:
                bucket["character_design_id"] = int(c.character_design_id)
                bucket["character_design_name"] = _translate_design_name(
                    c.character_design_id,
                    crew_map_es,
                    crew_map_en,
                    c.character_name,
                )
            char_level = _as_int(c.level)
            if char_level is not None:
                bucket["levels"].append(char_level)

        for key in ("player_low", "player_high"):
            players[key]["ships"] = _finalize_breakdown_buckets(players[key]["ships"])
            players[key]["rooms"] = _finalize_breakdown_buckets(players[key]["rooms"])
            players[key]["crew"] = _finalize_breakdown_buckets(players[key]["crew"])
            players[key]["total_battles_analyzed"] = len(replays)

        # Ship battle count is per-battle-per-side; ships fielded in more
        # battles are more "representative" of the player's current fleet.
        return {
            "player_low_user_id": low_user_id,
            "player_high_user_id": high_user_id,
            "battles_analyzed": len(replays),
            "battle_ids": battle_ids,
            "player_low": players["player_low"],
            "player_high": players["player_high"],
        }
    finally:
        db.close()


def _init_breakdown_player(user_id: int) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "ships": defaultdict(
            lambda: {
                "battles": 0,
                "ship_name": None,
                "ship_design_id": None,
                "ship_design_name": None,
                "levels": [],
                "power_scores": [],
            }
        ),
        "rooms": defaultdict(
            lambda: {
                "battles": 0,
                "room_design_id": None,
                "room_design_name": None,
            }
        ),
        "crew": defaultdict(
            lambda: {
                "battles": 0,
                "character_name": None,
                "character_design_id": None,
                "character_design_name": None,
                "levels": [],
            }
        ),
    }


def _finalize_breakdown_buckets(buckets: defaultdict) -> list[dict[str, Any]]:
    rows = []
    for _id, data in buckets.items():
        levels = [lv for lv in data.pop("levels", []) if lv is not None]
        avg_level = (sum(levels) / len(levels)) if levels else 0
        power_scores = [p for p in data.pop("power_scores", []) if p is not None]
        avg_power = (sum(power_scores) / len(power_scores)) if power_scores else 0
        data["avg_level"] = round(avg_level, 1)
        data["avg_power_score"] = round(avg_power, 1)
        data["id"] = _id
        rows.append(dict(data))
    rows.sort(
        key=lambda r: (
            -int(r.get("battles", 0)),
            str(
                r.get("ship_design_name")
                or r.get("room_design_name")
                or r.get("character_design_name")
                or ""
            ),
        )
    )
    return rows


def get_unique_player_pairs() -> list[dict[str, Any]]:
    """Get all unique player pairs with battle counts for H2H selection"""
    db = SessionLocal()
    try:
        pair_filters = [
            and_(
                PlayerMatchupStat.player_low_user_id == low_id,
                PlayerMatchupStat.player_high_user_id == high_id,
            )
            for low_id, high_id in db.query(
                PlayerMatchupStat.player_low_user_id,
                PlayerMatchupStat.player_high_user_id,
            )
            .distinct()
            .all()
        ]

        if not pair_filters:
            return []

        stats = db.query(PlayerMatchupStat).filter(or_(*pair_filters)).all()

        result = []
        for s in stats:
            result.append(
                {
                    "low_user_id": int(s.player_low_user_id),
                    "high_user_id": int(s.player_high_user_id),
                    "low_name": s.player_low_name,
                    "high_name": s.player_high_name,
                    "total_battles": int(s.total_battles or 0),
                    "low_wins": int(s.player_low_wins or 0),
                    "high_wins": int(s.player_high_wins or 0),
                }
            )
        return result
    finally:
        db.close()


def search_player_pairs(search: str) -> list[dict[str, Any]]:
    """Search player pairs by name or user_id"""
    db = SessionLocal()
    try:
        token = f"%{search.strip()}%"
        stats = (
            db.query(PlayerMatchupStat)
            .filter(
                or_(
                    PlayerMatchupStat.player_low_name.ilike(token),
                    PlayerMatchupStat.player_high_name.ilike(token),
                    cast(PlayerMatchupStat.player_low_user_id, String).ilike(token),
                    cast(PlayerMatchupStat.player_high_user_id, String).ilike(token),
                )
            )
            .all()
        )

        result = []
        for s in stats:
            result.append(
                {
                    "low_user_id": int(s.player_low_user_id),
                    "high_user_id": int(s.player_high_user_id),
                    "low_name": s.player_low_name,
                    "high_name": s.player_high_name,
                    "total_battles": int(s.total_battles or 0),
                    "low_wins": int(s.player_low_wins or 0),
                    "high_wins": int(s.player_high_wins or 0),
                }
            )
        return result
    finally:
        db.close()
