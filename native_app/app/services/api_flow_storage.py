from __future__ import annotations

import base64
import binascii
import gzip
import json
import re
import logging
import os
import unicodedata
import xml.etree.ElementTree as ET
from sqlite3 import OperationalError as SQLiteOperationalError
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any

from sqlalchemy import String, and_, cast, or_, text
from sqlalchemy.exc import OperationalError as SQLAlchemyOperationalError

from app.core.config import settings
from app.models.database import SessionLocal, engine
from app.models.pss_models import (
    ApiFlowEvent,
    BattleReplayCharacter,
    BattleReplayCommand,
    BattleReplayNormalized,
    BattleReplayRoom,
    BattleReplayShip,
    CrewDesign,
    PlayerMatchupLog,
    PlayerMatchupStat,
    RoomDesign,
    ShipDesign,
)

logger = logging.getLogger(__name__)

_SENSITIVE_HEADERS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-access-token",
    "x-auth-token",
    "proxy-authorization",
}


@dataclass
class ApiFlowFilters:
    search: str = ""
    method: str = ""
    status_min: int | None = None
    status_max: int | None = None
    only_errors: bool = False
    time_from: datetime | None = None
    time_to: datetime | None = None


@dataclass(frozen=True)
class BattleReplayListRow:
    id: int
    api_flow_event_id: int | None
    captured_at: datetime | None
    attacker_name: str | None
    attacker_trophy: int | None
    defender_name: str | None
    defender_trophy: int | None
    outcome_type: str | None
    win_minerals_result: int | None
    lose_minerals_result: int | None
    win_gas_result: int | None
    lose_gas_result: int | None
    win_trophy_result: int | None
    lose_trophy_result: int | None
    battle_id: int | None
    attacker_user_id: int | None
    defender_user_id: int | None


class ApiFlowRepository:
    _ALLOWED_DIRECTIONS = {"request", "response", "error"}
    _ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "CONNECT"}

    def __init__(self) -> None:
        self.body_max_chars = max(128, int(settings.API_FLOW_BODY_MAX_CHARS))
        self._recent_catalog_sync_count = 0

    def save_events(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0

        rows: list[ApiFlowEvent] = []
        rejected = 0
        for event in events:
            normalized = self._normalize_event(event)
            if not self._should_persist_event(normalized):
                rejected += 1
                continue
            if not self._validate_normalized_event(normalized):
                rejected += 1
                continue
            rows.append(ApiFlowEvent(**normalized))
        if rejected:
            logger.warning("event=api_flow_event_integrity_rejected count=%s", rejected)
        if not rows:
            return 0

        db = SessionLocal()
        try:
            db.add_all(rows)
            db.flush()
            battle_rows = self._build_battle_replay_rows(rows)
            if battle_rows:
                db.add_all(battle_rows)
                db.flush()
                child_rows = self._build_battle_replay_child_rows(rows, battle_rows)
                if child_rows:
                    self._persist_rows_one_by_one(db, child_rows)
                matchup_result = self._record_matchup_log_for_rows(db, battle_rows)
                affected_pairs = matchup_result["affected_pairs"]
                if affected_pairs:
                    self._prune_obsolete_replays_for_pairs(db, affected_pairs)
                    self._recompute_matchup_stats_for_pairs(db, affected_pairs)
            design_catalog_updated = self._sync_design_catalogs_from_saved_rows(db, rows)
            db.commit()
            if design_catalog_updated:
                self._recent_catalog_sync_count += int(design_catalog_updated)
                logger.info("event=design_catalogs_synced_from_save count=%s", design_catalog_updated)
            return len(rows)
        except (SQLiteOperationalError, SQLAlchemyOperationalError) as exc:
            db.rollback()
            if "database is locked" in str(exc).lower():
                logger.warning(
                    "event=api_flow_save_locked count=%s pending_retry=true",
                    len(events),
                )
                return 0
            logger.exception("event=api_flow_save_error count=%s", len(events))
            return 0
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_save_error count=%s", len(events))
            return 0
        finally:
            db.close()

    def _should_persist_event(self, normalized: dict[str, Any]) -> bool:
        path = str(normalized.get("path") or "").strip()
        if not path:
            return False
        base_path = path.split("?", 1)[0].rstrip("/") or "/"
        allowlist = settings.API_FLOW_CAPTURE_PATH_ALLOWLIST or ["/BattleService/GetBattle3"]
        for allowed in allowlist:
            allowed_base = str(allowed or "").split("?", 1)[0].rstrip("/") or "/"
            if base_path == allowed_base:
                return True
        return False

    def list_events(
        self,
        filters: ApiFlowFilters,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        db = SessionLocal()
        try:
            query = db.query(ApiFlowEvent)

            if filters.search:
                token = f"%{filters.search.strip()}%"
                query = query.filter(
                    or_(
                        ApiFlowEvent.host.ilike(token),
                        ApiFlowEvent.path.ilike(token),
                        ApiFlowEvent.url_full.ilike(token),
                    )
                )
            if filters.method:
                query = query.filter(ApiFlowEvent.method == filters.method)
            if filters.status_min is not None:
                query = query.filter(ApiFlowEvent.status_code >= filters.status_min)
            if filters.status_max is not None:
                query = query.filter(ApiFlowEvent.status_code <= filters.status_max)
            if filters.only_errors:
                query = query.filter(
                    or_(
                        ApiFlowEvent.error_text.isnot(None),
                        ApiFlowEvent.status_code >= 400,
                    )
                )
            if filters.time_from is not None:
                query = query.filter(ApiFlowEvent.captured_at >= filters.time_from)
            if filters.time_to is not None:
                query = query.filter(ApiFlowEvent.captured_at <= filters.time_to)

            total = query.count()
            page = max(0, page)
            page_size = max(1, page_size)
            rows = (
                query.order_by(ApiFlowEvent.captured_at.desc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )

            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "rows": [self._serialize_row(row) for row in rows],
            }
        finally:
            db.close()

    def purge(self, retention_days: int, max_db_mb: int) -> dict[str, int]:
        deleted_ttl = self.purge_by_ttl(retention_days)
        deleted_size = self.purge_by_size(max_db_mb)
        return {
            "deleted_ttl": deleted_ttl,
            "deleted_size": deleted_size,
        }

    def purge_by_ttl(self, retention_days: int) -> int:
        retention_days = max(1, int(retention_days))
        threshold = datetime.now(timezone.utc) - timedelta(days=retention_days)
        db = SessionLocal()
        try:
            event_ids = [
                row[0]
                for row in db.query(ApiFlowEvent.id)
                .filter(ApiFlowEvent.captured_at < threshold)
                .all()
            ]
            deleted = self._delete_events_and_normalized(db, event_ids)
            db.commit()
            return int(deleted or 0)
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_purge_ttl_error retention_days=%s", retention_days)
            return 0
        finally:
            db.close()

    def purge_by_size(self, max_db_mb: int, chunk_size: int = 1000) -> int:
        max_db_mb = max(16, int(max_db_mb))
        deleted_total = 0

        while self._current_db_size_mb() > float(max_db_mb):
            db = SessionLocal()
            try:
                oldest = (
                    db.query(ApiFlowEvent.id)
                    .order_by(ApiFlowEvent.captured_at.asc())
                    .limit(chunk_size)
                    .all()
                )
                if not oldest:
                    break
                oldest_ids = [row[0] for row in oldest]
                deleted = self._delete_events_and_normalized(db, oldest_ids)
                db.commit()
                deleted_total += int(deleted or 0)
                if deleted == 0:
                    break
            except Exception:
                db.rollback()
                logger.exception("event=api_flow_purge_size_error max_db_mb=%s", max_db_mb)
                break
            finally:
                db.close()

        # SQLite does not release file space on DELETE alone; compact after purging.
        if deleted_total > 0 and engine.dialect.name == "sqlite":
            self._vacuum_sqlite()

        current_size = self._current_db_size_mb()
        if current_size > float(max_db_mb):
            logger.warning(
                "event=api_flow_purge_size_target_not_met current_mb=%.2f max_mb=%s",
                current_size,
                max_db_mb,
            )
        return deleted_total

    def clear_events(self) -> int:
        db = SessionLocal()
        try:
            deleted = db.query(ApiFlowEvent).delete(synchronize_session=False)
            db.commit()
            return int(deleted or 0)
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_clear_error")
            return 0
        finally:
            db.close()

    def clear_battle_replays(self) -> int:
        db = SessionLocal()
        try:
            db.query(BattleReplayCommand).delete(synchronize_session=False)
            db.query(BattleReplayCharacter).delete(synchronize_session=False)
            db.query(BattleReplayRoom).delete(synchronize_session=False)
            db.query(BattleReplayShip).delete(synchronize_session=False)
            db.query(PlayerMatchupLog).delete(synchronize_session=False)
            db.query(PlayerMatchupStat).delete(synchronize_session=False)
            deleted = db.query(BattleReplayNormalized).delete(synchronize_session=False)
            db.commit()
            return int(deleted or 0)
        except Exception:
            db.rollback()
            logger.exception("event=battle_replay_clear_error")
            return 0
        finally:
            db.close()

    def delete_event(self, event_id: int | None) -> int:
        if event_id is None:
            return 0
        db = SessionLocal()
        try:
            replay = (
                db.query(BattleReplayNormalized)
                .filter(BattleReplayNormalized.api_flow_event_id == int(event_id))
                .first()
            )
            pair = (
                self._pair_key(replay.attacker_user_id, replay.defender_user_id)
                if replay is not None
                else None
            )
            battle_id = int(replay.battle_id) if replay is not None and replay.battle_id is not None else None
            deleted = self._delete_events_and_normalized(db, [int(event_id)])
            if pair is not None and battle_id is not None:
                db.query(PlayerMatchupLog).filter(
                    PlayerMatchupLog.player_low_user_id == pair[0],
                    PlayerMatchupLog.player_high_user_id == pair[1],
                    PlayerMatchupLog.battle_id == battle_id,
                ).delete(synchronize_session=False)
                self._recompute_matchup_stats_for_pairs(db, {pair})
            db.commit()
            return int(deleted or 0)
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_event_delete_error event_id=%s", event_id)
            return 0
        finally:
            db.close()

    def list_battle_replays(
        self,
        search: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        db = SessionLocal()
        try:
            query = db.query(BattleReplayNormalized)
            if search:
                token = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        BattleReplayNormalized.attacker_name.ilike(token),
                        BattleReplayNormalized.defender_name.ilike(token),
                        BattleReplayNormalized.outcome_type.ilike(token),
                        cast(BattleReplayNormalized.battle_id, String).ilike(token),
                    )
                )

            total = query.count()
            page = max(0, page)
            page_size = max(1, page_size)
            rows = (
                query.order_by(BattleReplayNormalized.captured_at.desc(), BattleReplayNormalized.id.desc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "rows": [self._serialize_battle_replay_row(row) for row in rows],
            }
        finally:
            db.close()

    def list_battle_replay_rows(
        self,
        search: str,
        page: int,
        page_size: int,
        time_from: datetime | None = None,
        time_to: datetime | None = None,
        outcome: str | None = None,
        trophy_min: int | None = None,
        trophy_max: int | None = None,
    ) -> tuple[int, list[BattleReplayListRow]]:
        db = SessionLocal()
        try:
            query = db.query(
                BattleReplayNormalized.id,
                BattleReplayNormalized.api_flow_event_id,
                BattleReplayNormalized.captured_at,
                BattleReplayNormalized.attacker_name,
                BattleReplayNormalized.attacker_trophy,
                BattleReplayNormalized.defender_name,
                BattleReplayNormalized.defender_trophy,
                BattleReplayNormalized.outcome_type,
                BattleReplayNormalized.win_minerals_result,
                BattleReplayNormalized.lose_minerals_result,
                BattleReplayNormalized.win_gas_result,
                BattleReplayNormalized.lose_gas_result,
                BattleReplayNormalized.win_trophy_result,
                BattleReplayNormalized.lose_trophy_result,
                BattleReplayNormalized.battle_id,
                BattleReplayNormalized.attacker_user_id,
                BattleReplayNormalized.defender_user_id,
            )
            if search:
                token = f"%{search.strip()}%"
                query = query.filter(
                    or_(
                        BattleReplayNormalized.attacker_name.ilike(token),
                        BattleReplayNormalized.defender_name.ilike(token),
                        BattleReplayNormalized.outcome_type.ilike(token),
                        cast(BattleReplayNormalized.battle_id, String).ilike(token),
                    )
                )
            if time_from is not None:
                query = query.filter(BattleReplayNormalized.captured_at >= time_from)
            if time_to is not None:
                query = query.filter(BattleReplayNormalized.captured_at <= time_to)
            if outcome:
                query = query.filter(BattleReplayNormalized.outcome_type == outcome)
            if trophy_min is not None:
                query = query.filter(
                    or_(
                        BattleReplayNormalized.attacker_trophy >= trophy_min,
                        BattleReplayNormalized.defender_trophy >= trophy_min,
                    )
                )
            if trophy_max is not None:
                query = query.filter(
                    or_(
                        BattleReplayNormalized.attacker_trophy <= trophy_max,
                        BattleReplayNormalized.defender_trophy <= trophy_max,
                    )
                )
            total = int(query.order_by(None).count())
            page = max(0, page)
            page_size = max(1, page_size)
            rows = (
                query.order_by(BattleReplayNormalized.captured_at.desc(), BattleReplayNormalized.id.desc())
                .offset(page * page_size)
                .limit(page_size)
                .all()
            )
            return total, [
                BattleReplayListRow(
                    id=int(row.id),
                    api_flow_event_id=int(row.api_flow_event_id) if row.api_flow_event_id is not None else None,
                    captured_at=row.captured_at,
                    attacker_name=row.attacker_name,
                    attacker_trophy=row.attacker_trophy,
                    defender_name=row.defender_name,
                    defender_trophy=row.defender_trophy,
                    outcome_type=row.outcome_type,
                    win_minerals_result=row.win_minerals_result,
                    lose_minerals_result=row.lose_minerals_result,
                    win_gas_result=row.win_gas_result,
                    lose_gas_result=row.lose_gas_result,
                    win_trophy_result=row.win_trophy_result,
                    lose_trophy_result=row.lose_trophy_result,
                    battle_id=row.battle_id,
                    attacker_user_id=row.attacker_user_id,
                    defender_user_id=row.defender_user_id,
                )
                for row in rows
            ]
        finally:
            db.close()

    def get_matchup_summaries_for_pairs(
        self,
        pairs: set[tuple[int, int]],
    ) -> dict[tuple[int, int], dict[str, Any]]:
        if not pairs:
            return {}
        db = SessionLocal()
        try:
            pair_filters = [
                and_(
                    PlayerMatchupStat.player_low_user_id == low_id,
                    PlayerMatchupStat.player_high_user_id == high_id,
                )
                for low_id, high_id in pairs
            ]
            stats_rows = (
                db.query(PlayerMatchupStat)
                .filter(or_(*pair_filters))
                .all()
                if pair_filters
                else []
            )
            out: dict[tuple[int, int], dict[str, Any]] = {}
            for row in stats_rows:
                key = (int(row.player_low_user_id), int(row.player_high_user_id))
                out[key] = {
                    "player_low_user_id": key[0],
                    "player_high_user_id": key[1],
                    "player_low_name": row.player_low_name,
                    "player_high_name": row.player_high_name,
                    "total_battles": int(row.total_battles or 0),
                    "player_low_wins": int(row.player_low_wins or 0),
                    "player_high_wins": int(row.player_high_wins or 0),
                    "unknown_results": int(row.unknown_results or 0),
                    "last_battle_id": row.last_battle_id,
                    "last_winner_user_id": row.last_winner_user_id,
                    "last_captured_at": (
                        row.last_captured_at.isoformat()
                        if row.last_captured_at is not None
                        else None
                    ),
                    "recent_log": [],
                }

            log_pair_filters = [
                and_(
                    PlayerMatchupLog.player_low_user_id == low_id,
                    PlayerMatchupLog.player_high_user_id == high_id,
                )
                for low_id, high_id in pairs
            ]
            log_rows = (
                db.query(PlayerMatchupLog)
                .filter(or_(*log_pair_filters))
                .order_by(
                    PlayerMatchupLog.player_low_user_id.asc(),
                    PlayerMatchupLog.player_high_user_id.asc(),
                    PlayerMatchupLog.captured_at.desc(),
                    PlayerMatchupLog.id.desc(),
                )
                .all()
                if log_pair_filters
                else []
            )
            logs_by_pair: dict[tuple[int, int], list[PlayerMatchupLog]] = {}
            for row in log_rows:
                key = (int(row.player_low_user_id), int(row.player_high_user_id))
                logs_by_pair.setdefault(key, []).append(row)

            for key in pairs:
                logs = logs_by_pair.get(key, [])
                if key not in out and logs:
                    low_wins = 0
                    high_wins = 0
                    unknown_results = 0
                    for log_row in logs:
                        winner_id = self._as_int(log_row.winner_user_id)
                        if winner_id == key[0]:
                            low_wins += 1
                        elif winner_id == key[1]:
                            high_wins += 1
                        else:
                            unknown_results += 1
                    latest = logs[0]
                    out[key] = {
                        "player_low_user_id": key[0],
                        "player_high_user_id": key[1],
                        "player_low_name": None,
                        "player_high_name": None,
                        "total_battles": len(logs),
                        "player_low_wins": low_wins,
                        "player_high_wins": high_wins,
                        "unknown_results": unknown_results,
                        "last_battle_id": latest.battle_id,
                        "last_winner_user_id": latest.winner_user_id,
                        "last_captured_at": (
                            latest.captured_at.isoformat()
                            if latest.captured_at is not None
                            else None
                        ),
                        "recent_log": [],
                    }
                summary = out.get(key)
                if summary is None:
                    continue
                summary["recent_log"] = [
                    {
                        "battle_id": row.battle_id,
                        "winner_user_id": row.winner_user_id,
                        "captured_at": row.captured_at.isoformat() if row.captured_at is not None else None,
                        "outcome_type": row.outcome_type,
                    }
                    for row in logs[:5]
                ]
            return out
        finally:
            db.close()

    def get_battle_replay_detail(self, battle_replay_id: int) -> dict[str, Any] | None:
        db = SessionLocal()
        try:
            replay = (
                db.query(BattleReplayNormalized)
                .filter(BattleReplayNormalized.id == int(battle_replay_id))
                .first()
            )
            if replay is None:
                return None

            api_flow_event = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.id == replay.api_flow_event_id)
                .first()
            )
            ships = (
                db.query(BattleReplayShip)
                .filter(BattleReplayShip.battle_replay_id == replay.id)
                .order_by(BattleReplayShip.id.asc())
                .all()
            )
            ship_design_ids = {
                int(row.ship_design_id)
                for row in ships
                if row.ship_design_id is not None
            }
            ship_design_map_en: dict[int, str] = {}
            ship_design_map_es: dict[int, str] = {}
            if ship_design_ids:
                design_rows = (
                    db.query(ShipDesign.ship_design_id, ShipDesign.name, ShipDesign.name_es)
                    .filter(ShipDesign.ship_design_id.in_(list(ship_design_ids)))
                    .all()
                )
                for design_id, name, name_es in design_rows:
                    if design_id is None:
                        continue
                    if name:
                        ship_design_map_en[int(design_id)] = str(name)
                    if name_es:
                        ship_design_map_es[int(design_id)] = str(name_es)
            rooms = (
                db.query(BattleReplayRoom)
                .filter(BattleReplayRoom.battle_replay_id == replay.id)
                .order_by(BattleReplayRoom.id.asc())
                .all()
            )
            room_design_ids = {
                int(row.room_design_id)
                for row in rooms
                if row.room_design_id is not None
            }
            room_design_map_en: dict[int, str] = {}
            room_design_map_es: dict[int, str] = {}
            if room_design_ids:
                try:
                    room_rows = (
                        db.query(RoomDesign.room_design_id, RoomDesign.name, RoomDesign.name_es)
                        .filter(RoomDesign.room_design_id.in_(list(room_design_ids)))
                        .all()
                    )
                    for design_id, name, name_es in room_rows:
                        if design_id is None:
                            continue
                        if name:
                            room_design_map_en[int(design_id)] = str(name)
                        if name_es:
                            room_design_map_es[int(design_id)] = str(name_es)
                except SQLAlchemyOperationalError:
                    logger.warning("event=room_designs_lookup_unavailable")
            characters = (
                db.query(BattleReplayCharacter)
                .filter(BattleReplayCharacter.battle_replay_id == replay.id)
                .order_by(BattleReplayCharacter.id.asc())
                .all()
            )
            character_design_ids = {
                int(row.character_design_id)
                for row in characters
                if row.character_design_id is not None
            }
            character_design_map_en: dict[int, str] = {}
            character_design_map_es: dict[int, str] = {}
            if character_design_ids:
                try:
                    character_rows = (
                        db.query(CrewDesign.crew_design_id, CrewDesign.name, CrewDesign.name_es)
                        .filter(CrewDesign.crew_design_id.in_(list(character_design_ids)))
                        .all()
                    )
                    for design_id, name, name_es in character_rows:
                        if design_id is None:
                            continue
                        if name:
                            character_design_map_en[int(design_id)] = str(name)
                        if name_es:
                            character_design_map_es[int(design_id)] = str(name_es)
                except SQLAlchemyOperationalError:
                    logger.warning("event=crew_designs_lookup_unavailable")
            commands = (
                db.query(BattleReplayCommand)
                .filter(BattleReplayCommand.battle_replay_id == replay.id)
                .order_by(BattleReplayCommand.command_order.asc(), BattleReplayCommand.id.asc())
                .all()
            )
            matchup_summary: dict[str, Any] | None = None
            matchup_recent_log: list[dict[str, Any]] = []
            pair = self._pair_key(replay.attacker_user_id, replay.defender_user_id)
            if pair is not None:
                low_id, high_id = pair
                stat = (
                    db.query(PlayerMatchupStat)
                    .filter(
                        PlayerMatchupStat.player_low_user_id == low_id,
                        PlayerMatchupStat.player_high_user_id == high_id,
                    )
                    .first()
                )
                low_name = replay.attacker_name if replay.attacker_user_id == low_id else replay.defender_name
                high_name = replay.attacker_name if replay.attacker_user_id == high_id else replay.defender_name
                if stat is not None:
                    matchup_summary = {
                        "player_low_user_id": int(stat.player_low_user_id),
                        "player_high_user_id": int(stat.player_high_user_id),
                        "player_low_name": stat.player_low_name or low_name,
                        "player_high_name": stat.player_high_name or high_name,
                        "total_battles": int(stat.total_battles or 0),
                        "player_low_wins": int(stat.player_low_wins or 0),
                        "player_high_wins": int(stat.player_high_wins or 0),
                        "unknown_results": int(stat.unknown_results or 0),
                        "last_battle_id": stat.last_battle_id,
                        "last_winner_user_id": stat.last_winner_user_id,
                        "last_captured_at": (
                            stat.last_captured_at.isoformat()
                            if stat.last_captured_at is not None
                            else None
                        ),
                    }

                recent_logs = (
                    db.query(PlayerMatchupLog)
                    .filter(
                        PlayerMatchupLog.player_low_user_id == low_id,
                        PlayerMatchupLog.player_high_user_id == high_id,
                    )
                    .order_by(PlayerMatchupLog.captured_at.desc(), PlayerMatchupLog.id.desc())
                    .limit(5)
                    .all()
                )
                matchup_recent_log = [
                    {
                        "battle_id": row.battle_id,
                        "winner_user_id": row.winner_user_id,
                        "captured_at": row.captured_at.isoformat() if row.captured_at is not None else None,
                        "outcome_type": row.outcome_type,
                    }
                    for row in recent_logs
                ]
            return {
                "replay": self._serialize_battle_replay_row(replay),
                "api_flow_event": self._serialize_row(api_flow_event) if api_flow_event else None,
                "ships": [
                    self._serialize_battle_replay_ship_row(
                        row,
                        ship_design_map_es,
                        ship_design_map_en,
                    )
                    for row in ships
                ],
                "rooms": [
                    self._serialize_battle_replay_room_row(
                        row,
                        room_design_map_es,
                        room_design_map_en,
                    )
                    for row in rooms
                ],
                "characters": [
                    self._serialize_battle_replay_character_row(
                        row,
                        character_design_map_es,
                        character_design_map_en,
                    )
                    for row in characters
                ],
                "commands": [self._serialize_battle_replay_command_row(row) for row in commands],
                "matchup_summary": matchup_summary,
                "matchup_recent_log": matchup_recent_log,
            }
        finally:
            db.close()

    def sync_battle_replays_from_api_flow(self, batch_size: int = 500, max_event_id: int | None = None) -> int:
        db = SessionLocal()
        inserted = 0
        try:
            last_seen_id = 0
            while True:
                query = (
                    db.query(ApiFlowEvent)
                    .outerjoin(
                        BattleReplayNormalized,
                        BattleReplayNormalized.api_flow_event_id == ApiFlowEvent.id,
                    )
                    .filter(BattleReplayNormalized.id.is_(None))
                    .filter(ApiFlowEvent.path.like("/BattleService/GetBattle3%"))
                    .filter(ApiFlowEvent.response_body_cleaned.isnot(None))
                    .filter(ApiFlowEvent.id > last_seen_id)
                )
                if max_event_id is not None:
                    query = query.filter(ApiFlowEvent.id <= int(max_event_id))
                candidates = query.order_by(ApiFlowEvent.id.asc()).limit(max(1, batch_size)).all()
                if not candidates:
                    return inserted

                last_seen_id = candidates[-1].id
                new_rows = self._build_battle_replay_rows(candidates)
                if not new_rows:
                    continue

                db.add_all(new_rows)
                db.flush()
                child_rows = self._build_battle_replay_child_rows(candidates, new_rows)
                if child_rows:
                    self._persist_rows_one_by_one(db, child_rows)
                matchup_result = self._record_matchup_log_for_rows(db, new_rows)
                affected_pairs = matchup_result["affected_pairs"]
                if affected_pairs:
                    self._prune_obsolete_replays_for_pairs(db, affected_pairs)
                    self._recompute_matchup_stats_for_pairs(db, affected_pairs)
                db.commit()
                inserted += len(new_rows)
                return inserted
        except Exception:
            db.rollback()
            logger.exception("event=battle_replay_sync_error")
            return inserted
        finally:
            db.close()

    def backfill_matchup_history_and_prune(self, batch_size_pairs: int = 200) -> dict[str, int]:
        db = SessionLocal()
        metrics = {
            "inserted_logs": 0,
            "updated_pairs": 0,
            "deleted_obsolete_replays": 0,
        }
        try:
            replay_rows = (
                db.query(BattleReplayNormalized)
                .order_by(BattleReplayNormalized.id.asc())
                .all()
            )
            log_result = self._record_matchup_log_for_rows(db, replay_rows)
            metrics["inserted_logs"] = int(log_result["inserted_logs"])

            affected_pairs = set(log_result["affected_pairs"])
            pair_rows = (
                db.query(PlayerMatchupLog.player_low_user_id, PlayerMatchupLog.player_high_user_id)
                .distinct()
                .all()
            )
            affected_pairs.update(
                {
                    (int(row.player_low_user_id), int(row.player_high_user_id))
                    for row in pair_rows
                }
            )

            pair_list = sorted(affected_pairs)
            pair_batch_size = max(1, int(batch_size_pairs))
            if not pair_list:
                db.query(PlayerMatchupStat).delete(synchronize_session=False)
            for index in range(0, len(pair_list), pair_batch_size):
                chunk_pairs = set(pair_list[index : index + pair_batch_size])
                metrics["deleted_obsolete_replays"] += self._prune_obsolete_replays_for_pairs(db, chunk_pairs)
                metrics["updated_pairs"] += self._recompute_matchup_stats_for_pairs(db, chunk_pairs)

            db.commit()
            logger.info(
                "event=matchup_backfill_completed inserted_logs=%s updated_pairs=%s deleted_obsolete_replays=%s",
                metrics["inserted_logs"],
                metrics["updated_pairs"],
                metrics["deleted_obsolete_replays"],
            )
            return metrics
        except Exception:
            db.rollback()
            logger.exception("event=matchup_backfill_error")
            return metrics
        finally:
            db.close()

    def get_startup_sync_snapshot(self) -> dict[str, int]:
        db = SessionLocal()
        try:
            max_event_id = db.query(ApiFlowEvent.id).order_by(ApiFlowEvent.id.desc()).limit(1).scalar() or 0
            max_replay_id = (
                db.query(BattleReplayNormalized.id)
                .order_by(BattleReplayNormalized.id.desc())
                .limit(1)
                .scalar()
                or 0
            )
            return {
                "max_event_id": int(max_event_id),
                "max_replay_id": int(max_replay_id),
            }
        finally:
            db.close()

    def backfill_response_body_cleaned(self, batch_size: int = 100, max_event_id: int | None = None) -> int:
        db = SessionLocal()
        updated = 0
        try:
            query = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.path.like("/BattleService/GetBattle3%"))
                .filter(
                    or_(
                        ApiFlowEvent.response_body_cleaned.is_(None),
                        ApiFlowEvent.response_body_cleaned == "",
                    )
                )
            )
            if max_event_id is not None:
                query = query.filter(ApiFlowEvent.id <= int(max_event_id))
            candidates = query.order_by(ApiFlowEvent.id.asc()).limit(max(1, batch_size)).all()
            if not candidates:
                return 0

            for row in candidates:
                cleaned = self._clean_response_body(row.response_body_preview)
                if not cleaned:
                    continue
                row.response_body_cleaned = cleaned
                updated += 1

            if updated > 0:
                db.commit()
            return updated
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_cleaned_backfill_error")
            return 0
        finally:
            db.close()

    def backfill_room_attributes(self, batch_size: int = 100, max_replay_id: int | None = None) -> int:
        db = SessionLocal()
        updated = 0
        try:
            last_seen_id = 0
            while True:
                query = (
                    db.query(BattleReplayNormalized, ApiFlowEvent)
                    .join(ApiFlowEvent, ApiFlowEvent.id == BattleReplayNormalized.api_flow_event_id)
                    .filter(ApiFlowEvent.response_body_cleaned.isnot(None))
                    .filter(BattleReplayNormalized.id > last_seen_id)
                )
                if max_replay_id is not None:
                    query = query.filter(BattleReplayNormalized.id <= int(max_replay_id))
                candidates = query.order_by(BattleReplayNormalized.id.asc()).limit(max(1, batch_size)).all()
                if not candidates:
                    break
                for replay, api_flow_event in candidates:
                    last_seen_id = max(last_seen_id, int(replay.id))
                    parsed = self._extract_battle_nodes_from_cleaned(api_flow_event.response_body_cleaned)
                    if parsed is None:
                        continue
                    new_rows = self._build_room_rows_for_replay(replay.id, parsed)
                    if not new_rows:
                        continue
                    existing_rows = (
                        db.query(BattleReplayRoom)
                        .filter(BattleReplayRoom.battle_replay_id == replay.id)
                        .all()
                    )
                    by_key: dict[tuple[str, int | None, int | None], BattleReplayRoom] = {}
                    for row in existing_rows:
                        key = (str(row.side or ""), row.room_id, row.ship_id)
                        by_key[key] = row
                    for new_row in new_rows:
                        key = (str(new_row.side or ""), new_row.room_id, new_row.ship_id)
                        existing = by_key.get(key)
                        if existing is None:
                            continue
                        existing.room_attributes_json = self._normalize_room_attributes(
                            new_row.room_attributes_json or {}
                        )
                        existing.row = new_row.row
                        existing.column = new_row.column
                        existing.room_status = new_row.room_status
                        updated += 1
                if updated > 0:
                    db.commit()
            return updated
        except Exception:
            db.rollback()
            logger.exception("event=room_attributes_backfill_error")
            return updated
        finally:
            db.close()

    def sync_battle_replay_children(self, batch_size: int = 200, max_replay_id: int | None = None) -> int:
        db = SessionLocal()
        inserted = 0
        try:
            query = (
                db.query(BattleReplayNormalized)
                .outerjoin(
                    BattleReplayShip,
                    BattleReplayShip.battle_replay_id == BattleReplayNormalized.id,
                )
                .filter(BattleReplayShip.id.is_(None))
            )
            if max_replay_id is not None:
                query = query.filter(BattleReplayNormalized.id <= int(max_replay_id))
            parents = query.order_by(BattleReplayNormalized.id.asc()).limit(max(1, batch_size)).all()
            if not parents:
                return 0

            parent_map = {row.api_flow_event_id: row for row in parents}
            api_flow_rows = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.id.in_(list(parent_map.keys())))
                .all()
            )
            if not api_flow_rows:
                return 0

            for api_flow_row in api_flow_rows:
                battle_row = parent_map.get(api_flow_row.id)
                if battle_row is None:
                    continue
                child_rows = self._build_battle_replay_child_rows([api_flow_row], [battle_row])
                if not child_rows:
                    continue
                try:
                    self._persist_rows_one_by_one(db, child_rows)
                    db.commit()
                    inserted += len(child_rows)
                except Exception:
                    db.rollback()
                    logger.exception(
                        "event=battle_replay_child_sync_error api_flow_event_id=%s battle_replay_id=%s",
                        api_flow_row.id,
                        battle_row.id,
                    )
            return inserted
        except Exception:
            db.rollback()
            logger.exception("event=battle_replay_child_sync_query_error")
            return inserted
        finally:
            db.close()

    def sync_ship_designs_from_api_flow(self, limit_events: int = 1) -> int:
        db = SessionLocal()
        try:
            candidates = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.path.like("/DesignService/ListAllStaticDesigns2%"))
                .filter(ApiFlowEvent.response_body_preview.isnot(None))
                .order_by(ApiFlowEvent.id.desc())
                .limit(max(1, int(limit_events)))
                .all()
            )
            if not candidates:
                return 0
            updated = self._sync_design_catalogs_from_saved_rows(db, candidates)
            if updated > 0:
                db.commit()
                self._recent_catalog_sync_count += int(updated)
            return updated
        except Exception:
            db.rollback()
            logger.exception("event=ship_designs_sync_error")
            return 0
        finally:
            db.close()

    def pop_recent_catalog_sync_count(self) -> int:
        value = int(self._recent_catalog_sync_count)
        self._recent_catalog_sync_count = 0
        return value

    def _current_db_size_mb(self) -> float:
        if engine.dialect.name != "sqlite":
            return 0.0

        try:
            with engine.begin() as conn:
                rows = conn.execute(text("PRAGMA database_list")).fetchall()
            db_paths = [str(row[2]) for row in rows if len(row) >= 3 and row[2]]
            if not db_paths:
                return 0.0
            db_path = db_paths[0]
            if not os.path.exists(db_path):
                return 0.0
            size_bytes = os.path.getsize(db_path)
            return size_bytes / (1024 * 1024)
        except Exception:
            logger.exception("event=api_flow_db_size_error")
            return 0.0

    def _vacuum_sqlite(self) -> None:
        try:
            with engine.connect() as conn:
                conn = conn.execution_options(isolation_level="AUTOCOMMIT")
                conn.exec_driver_sql("VACUUM")
        except Exception:
            logger.exception("event=api_flow_vacuum_error")

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        request_headers = self._redact_headers(event.get("request_headers_json"))
        response_headers = self._redact_headers(event.get("response_headers_json"))

        captured_at = self._parse_datetime(event.get("captured_at"))
        if captured_at is None:
            captured_at = datetime.now(timezone.utc)

        query_value = event.get("query")
        if query_value is None:
            query_value = ""
        response_body_preview = self._as_full_text(event.get("response_body_preview"))
        response_body_cleaned = self._clean_response_body(response_body_preview)

        normalized = {
            "session_id": str(event.get("session_id") or "unknown")[:64],
            "captured_at": captured_at,
            "direction": self._normalize_direction(event.get("direction")),
            "method": self._normalize_method(event.get("method")),
            "scheme": self._as_text(event.get("scheme"), 16),
            "host": self._as_text(event.get("host"), 255),
            "port": self._as_int(event.get("port")),
            "path": self._as_text(event.get("path"), 2048),
            "query": self._as_text(query_value, 4096),
            "url_full": self._as_text(event.get("url_full"), 4096),
            "status_code": self._as_int(event.get("status_code")),
            "duration_ms": self._as_int(event.get("duration_ms")),
            "request_headers_json": request_headers,
            "response_headers_json": response_headers,
            "request_body_preview": self._truncate(event.get("request_body_preview")),
            "response_body_preview": response_body_preview,
            "response_body_cleaned": response_body_cleaned,
            "request_size_bytes": self._as_int(event.get("request_size_bytes")),
            "response_size_bytes": self._as_int(event.get("response_size_bytes")),
            "content_type_request": self._as_text(event.get("content_type_request"), 255),
            "content_type_response": self._as_text(event.get("content_type_response"), 255),
            "tls": bool(event.get("tls")),
            "error_text": self._as_text(event.get("error_text"), 2048),
            "game_process_hint": self._as_text(event.get("game_process_hint"), 255),
            "flow_hash": self._as_text(event.get("flow_hash"), 100),
        }
        return normalized

    def _normalize_direction(self, value: Any) -> str:
        direction = str(value or "response").strip().lower()
        if direction not in self._ALLOWED_DIRECTIONS:
            return "response"
        return direction

    def _normalize_method(self, value: Any) -> str | None:
        method = self._as_text(value, 16)
        if method is None:
            return None
        normalized = method.strip().upper()
        if not normalized:
            return None
        return normalized

    def _validate_normalized_event(self, normalized: dict[str, Any]) -> bool:
        direction = normalized.get("direction")
        if direction not in self._ALLOWED_DIRECTIONS:
            return False

        method = normalized.get("method")
        if method is not None and method not in self._ALLOWED_METHODS:
            return False

        status_code = normalized.get("status_code")
        if status_code is not None and not (100 <= int(status_code) <= 599):
            return False

        port = normalized.get("port")
        if port is not None and not (1 <= int(port) <= 65535):
            return False

        host = normalized.get("host")
        path = normalized.get("path")
        url_full = normalized.get("url_full")
        if not any((host, path, url_full)):
            return False

        return True

    def _serialize_row(self, row: ApiFlowEvent) -> dict[str, Any]:
        return {
            "id": row.id,
            "session_id": row.session_id,
            "captured_at": row.captured_at.isoformat() if row.captured_at else None,
            "direction": row.direction,
            "method": row.method,
            "scheme": row.scheme,
            "host": row.host,
            "port": row.port,
            "path": row.path,
            "query": row.query,
            "url_full": row.url_full,
            "status_code": row.status_code,
            "duration_ms": row.duration_ms,
            "request_headers_json": row.request_headers_json or {},
            "response_headers_json": row.response_headers_json or {},
            "request_body_preview": row.request_body_preview,
            "response_body_preview": row.response_body_preview,
            "response_body_cleaned": row.response_body_cleaned,
            "request_size_bytes": row.request_size_bytes,
            "response_size_bytes": row.response_size_bytes,
            "content_type_request": row.content_type_request,
            "content_type_response": row.content_type_response,
            "tls": row.tls,
            "error_text": row.error_text,
            "game_process_hint": row.game_process_hint,
            "flow_hash": row.flow_hash,
        }

    def _truncate(self, value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value)
        if len(text_value) <= self.body_max_chars:
            return text_value
        return text_value[: self.body_max_chars] + "..."

    def _as_full_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text_value = str(value)
        if not text_value:
            return None
        return text_value

    def _as_text(self, value: Any, max_len: int) -> str | None:
        if value is None:
            return None
        text_value = str(value)
        if not text_value:
            return None
        return text_value[:max_len]

    def _as_int(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(float(str(value).strip()))
        except (TypeError, ValueError):
            return None

    def _as_float(self, value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            return float(str(value).strip())
        except (TypeError, ValueError):
            return None

    def _parse_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value

        try:
            text_value = str(value).strip()
            if text_value.endswith("Z"):
                text_value = text_value[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text_value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed
        except Exception:
            return None

    def _redact_headers(self, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}

        cleaned: dict[str, str] = {}
        for header_key, header_value in value.items():
            key = str(header_key)
            if key.lower() in _SENSITIVE_HEADERS:
                cleaned[key] = "***REDACTED***"
                continue
            cleaned[key] = self._truncate_header_value(header_value)
        return cleaned

    def _truncate_header_value(self, value: Any) -> str:
        if value is None:
            return ""
        text_value = str(value)
        if len(text_value) <= 512:
            return text_value
        return text_value[:512] + "..."

    def _clean_response_body(self, response_body_preview: str | None) -> str | None:
        if not response_body_preview:
            return None

        xml_text = str(response_body_preview).strip()
        if not xml_text:
            return None

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return self._normalize_text(unescape(xml_text))

        cleaned_tree = self._xml_to_clean_dict(root)
        return self._normalize_text(json.dumps(cleaned_tree, ensure_ascii=False, indent=2))

    def _xml_to_clean_dict(self, node: ET.Element) -> dict[str, Any]:
        attributes: dict[str, Any] = {}
        for key, value in node.attrib.items():
            decoded_value = self._normalize_text(unescape(str(value)))
            if decoded_value is not None and decoded_value.strip().startswith("<") and decoded_value.strip().endswith(">"):
                nested = self._try_parse_nested_xml(decoded_value)
                attributes[key] = nested if nested is not None else decoded_value
            else:
                attributes[key] = decoded_value

        children = [self._xml_to_clean_dict(child) for child in list(node)]
        text_value = self._normalize_text(node.text)
        result: dict[str, Any] = {"tag": node.tag}
        if attributes:
            result["attributes"] = attributes
        if text_value:
            result["text"] = text_value
        if children:
            result["children"] = children
        return result

    def _try_parse_nested_xml(self, raw_xml: str) -> dict[str, Any] | None:
        try:
            nested_root = ET.fromstring(raw_xml)
            return self._xml_to_clean_dict(nested_root)
        except Exception:
            return None

    def _normalize_text(self, value: Any) -> str | None:
        if value is None:
            return None
        normalized = unicodedata.normalize("NFKC", str(value))
        normalized = self._repair_mojibake_text(normalized)
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
        if not normalized:
            return None
        return normalized

    def _repair_mojibake_text(self, value: str) -> str:
        text = str(value)
        if not text:
            return text
        suspicious_markers = ("Ã", "Â", "æ", "ç", "ð", "ã", "œ", "š")
        if not any(marker in text for marker in suspicious_markers):
            return text
        try:
            repaired = text.encode("latin1").decode("utf-8")
        except Exception:
            return text
        return repaired if repaired.strip() else text

    def _build_battle_replay_rows(self, rows: list[ApiFlowEvent]) -> list[BattleReplayNormalized]:
        out: list[BattleReplayNormalized] = []
        for row in rows:
            if not row.path or not row.path.startswith("/BattleService/GetBattle3"):
                continue
            normalized = self._extract_battle_replay_normalized_from_cleaned(row.response_body_cleaned)
            if normalized is None:
                continue
            normalized["api_flow_event_id"] = row.id
            normalized["captured_at"] = row.captured_at
            out.append(BattleReplayNormalized(**normalized))
        return out

    def _build_battle_replay_child_rows(
        self,
        api_flow_rows: list[ApiFlowEvent],
        battle_rows: list[BattleReplayNormalized],
    ) -> list[Any]:
        battle_by_event_id = {row.api_flow_event_id: row for row in battle_rows}
        out: list[Any] = []

        for api_flow_row in api_flow_rows:
            battle_row = battle_by_event_id.get(api_flow_row.id)
            if battle_row is None:
                continue
            parsed = self._extract_battle_nodes_from_cleaned(api_flow_row.response_body_cleaned)
            if parsed is None:
                continue

            out.extend(self._build_ship_rows_for_replay(battle_row.id, parsed))
            out.extend(self._build_room_rows_for_replay(battle_row.id, parsed))
            out.extend(self._build_character_rows_for_replay(battle_row.id, parsed))
            out.extend(self._build_command_rows_for_replay(battle_row.id, parsed))

        return out

    def _serialize_battle_replay_row(self, row: BattleReplayNormalized) -> dict[str, Any]:
        return {
            "id": row.id,
            "api_flow_event_id": row.api_flow_event_id,
            "battle_id": row.battle_id,
            "captured_at": row.captured_at.isoformat() if row.captured_at else None,
            "attacking_ship_id": row.attacking_ship_id,
            "defending_ship_id": row.defending_ship_id,
            "outcome_type": row.outcome_type,
            "client_outcome_type": row.client_outcome_type,
            "win_trophy_result": row.win_trophy_result,
            "win_minerals_result": row.win_minerals_result,
            "win_gas_result": row.win_gas_result,
            "lose_trophy_result": row.lose_trophy_result,
            "lose_minerals_result": row.lose_minerals_result,
            "lose_gas_result": row.lose_gas_result,
            "battle_end_frame": row.battle_end_frame,
            "client_end_frame": row.client_end_frame,
            "attacker_user_id": row.attacker_user_id,
            "attacker_name": self._normalize_text(row.attacker_name),
            "attacker_trophy": row.attacker_trophy,
            "defender_user_id": row.defender_user_id,
            "defender_name": self._normalize_text(row.defender_name),
            "defender_trophy": row.defender_trophy,
            "battle_attributes_json": row.battle_attributes_json,
            "attacker_user_attributes_json": row.attacker_user_attributes_json,
            "defender_user_attributes_json": row.defender_user_attributes_json,
        }

    def _serialize_battle_replay_ship_row(
        self,
        row: BattleReplayShip,
        ship_design_map_es: dict[int, str] | None = None,
        ship_design_map_en: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        design_name = self._translate_design_name(
            row.ship_design_id,
            ship_design_map_es,
            ship_design_map_en,
            row.ship_name,
        )
        return {
            "id": row.id,
            "battle_replay_id": row.battle_replay_id,
            "side": row.side,
            "ship_id": row.ship_id,
            "ship_design_id": row.ship_design_id,
            "ship_design_name": design_name,
            "ship_name": self._normalize_text(row.ship_name),
            "ship_level": row.ship_level,
            "power_score": row.power_score,
            "hp": row.hp,
            "ship_status": row.ship_status,
            "ship_attributes_json": row.ship_attributes_json,
        }

    def _serialize_battle_replay_room_row(
        self,
        row: BattleReplayRoom,
        room_design_map_es: dict[int, str] | None = None,
        room_design_map_en: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        design_name = self._translate_design_name(
            row.room_design_id,
            room_design_map_es,
            room_design_map_en,
            None,
        )
        return {
            "id": row.id,
            "battle_replay_id": row.battle_replay_id,
            "side": row.side,
            "room_id": row.room_id,
            "room_design_id": row.room_design_id,
            "room_design_name": design_name,
            "ship_id": row.ship_id,
            "row": row.row,
            "column": row.column,
            "room_status": row.room_status,
            "room_attributes_json": row.room_attributes_json,
        }

    def _serialize_battle_replay_character_row(
        self,
        row: BattleReplayCharacter,
        character_design_map_es: dict[int, str] | None = None,
        character_design_map_en: dict[int, str] | None = None,
    ) -> dict[str, Any]:
        design_name = self._translate_design_name(
            row.character_design_id,
            character_design_map_es,
            character_design_map_en,
            row.character_name,
        )
        return {
            "id": row.id,
            "battle_replay_id": row.battle_replay_id,
            "side": row.side,
            "character_id": row.character_id,
            "ship_id": row.ship_id,
            "character_design_id": row.character_design_id,
            "character_design_name": design_name,
            "character_name": self._normalize_text(row.character_name),
            "level": row.level,
            "xp": row.xp,
            "character_attributes_json": row.character_attributes_json,
        }

    def _serialize_battle_replay_command_row(self, row: BattleReplayCommand) -> dict[str, Any]:
        return {
            "id": row.id,
            "battle_replay_id": row.battle_replay_id,
            "command_order": row.command_order,
            "command_tag": row.command_tag,
            "user_id": row.user_id,
            "ship_id": row.ship_id,
            "room_id": row.room_id,
            "character_id": row.character_id,
            "command_attributes_json": row.command_attributes_json,
        }

    def _translate_design_name(
        self,
        design_id: int | None,
        map_es: dict[int, str] | None,
        map_en: dict[int, str] | None,
        raw_name: str | None,
    ) -> str:
        if design_id is not None:
            if map_es:
                value = map_es.get(int(design_id))
                if value and str(value).strip():
                    return self._normalize_text(value) or str(value).strip()
            if map_en:
                value = map_en.get(int(design_id))
                if value and str(value).strip():
                    return self._normalize_text(value) or str(value).strip()
        if raw_name and str(raw_name).strip():
            return self._normalize_text(raw_name) or str(raw_name).strip()
        if design_id is not None:
            return str(design_id)
        return "Sin traduccion"

    def _pick_design_name_es(self, attrs: dict[str, Any], base_key: str) -> str | None:
        candidates = [
            f"{base_key}ES",
            f"{base_key}Es",
            f"{base_key}_ES",
            f"{base_key}_Es",
            f"{base_key}Spanish",
            f"{base_key}_Spanish",
        ]
        for key in candidates:
            if key in attrs and attrs.get(key):
                return str(attrs.get(key))
        return None

    def _extract_battle_replay_normalized_from_cleaned(
        self, response_body_cleaned: str | None
    ) -> dict[str, Any] | None:
        parsed = self._extract_battle_nodes_from_cleaned(response_body_cleaned)
        if parsed is None:
            return None

        battle_attrs = parsed["battle_attrs"]
        battle_id = self._as_int(battle_attrs.get("BattleId"))
        if battle_id is None:
            return None

        attacker_user_attrs = parsed["attacker_user_attrs"]
        defender_user_attrs = parsed["defender_user_attrs"]

        return {
            "battle_id": battle_id,
            "attacking_ship_id": self._as_int(battle_attrs.get("AttackingShipId")),
            "defending_ship_id": self._as_int(battle_attrs.get("DefendingShipId")),
            "outcome_type": self._as_text(battle_attrs.get("OutcomeType"), 64),
            "client_outcome_type": self._as_text(battle_attrs.get("ClientOutcomeType"), 64),
            "win_trophy_result": self._as_int(battle_attrs.get("WinTrophyResult")),
            "win_minerals_result": self._as_int(battle_attrs.get("WinMineralsResult")),
            "win_gas_result": self._as_int(battle_attrs.get("WinGasResult")),
            "lose_trophy_result": self._as_int(battle_attrs.get("LoseTrophyResult")),
            "lose_minerals_result": self._as_int(battle_attrs.get("LoseMineralsResult")),
            "lose_gas_result": self._as_int(battle_attrs.get("LoseGasResult")),
            "battle_end_frame": self._as_int(battle_attrs.get("BattleEndFrame")),
            "client_end_frame": self._as_int(battle_attrs.get("ClientEndFrame")),
            "attacker_user_id": self._as_int(attacker_user_attrs.get("Id")),
            "attacker_name": self._as_text(self._normalize_text(attacker_user_attrs.get("Name")), 255),
            "attacker_trophy": self._as_int(attacker_user_attrs.get("Trophy")),
            "defender_user_id": self._as_int(defender_user_attrs.get("Id")),
            "defender_name": self._as_text(self._normalize_text(defender_user_attrs.get("Name")), 255),
            "defender_trophy": self._as_int(defender_user_attrs.get("Trophy")),
            "battle_attributes_json": battle_attrs,
            "attacker_user_attributes_json": attacker_user_attrs,
            "defender_user_attributes_json": defender_user_attrs,
        }

    def _extract_battle_nodes_from_cleaned(
        self, response_body_cleaned: str | None
    ) -> dict[str, Any] | None:
        if not response_body_cleaned:
            return None
        try:
            payload = json.loads(response_body_cleaned)
        except Exception:
            return None

        battle_node = self._find_first_node_by_tag(payload, "Battle")
        if battle_node is None:
            return None
        battle_attrs = battle_node.get("attributes")
        if not isinstance(battle_attrs, dict):
            return None

        attacker_user_attrs = self._extract_nested_attrs(battle_attrs.get("AttackingUserXml"))
        defender_user_attrs = self._extract_nested_attrs(battle_attrs.get("DefendingUserXml"))
        attacker_ship_node = self._extract_nested_node(battle_attrs.get("AttackingShipXml"))
        defender_ship_node = self._extract_nested_node(battle_attrs.get("DefendingShipXml"))
        commands_node = self._extract_nested_node(battle_attrs.get("Commands"))
        return {
            "payload": payload,
            "battle_node": battle_node,
            "battle_attrs": battle_attrs,
            "attacker_user_attrs": attacker_user_attrs,
            "defender_user_attrs": defender_user_attrs,
            "attacker_ship_node": attacker_ship_node,
            "defender_ship_node": defender_ship_node,
            "commands_node": commands_node,
        }

    def _find_first_node_by_tag(self, node: Any, tag: str) -> dict[str, Any] | None:
        if isinstance(node, dict):
            if node.get("tag") == tag:
                return node
            for value in node.values():
                found = self._find_first_node_by_tag(value, tag)
                if found is not None:
                    return found
            return None
        if isinstance(node, list):
            for item in node:
                found = self._find_first_node_by_tag(item, tag)
                if found is not None:
                    return found
            return None
        return None

    def _extract_nested_attrs(self, nested_node: Any) -> dict[str, Any]:
        if isinstance(nested_node, dict):
            attrs = nested_node.get("attributes")
            if isinstance(attrs, dict):
                return attrs
        return {}

    def _extract_nested_node(self, nested_node: Any) -> dict[str, Any] | None:
        if isinstance(nested_node, dict):
            return nested_node
        return None

    def _build_ship_rows_for_replay(self, battle_replay_id: int, parsed: dict[str, Any]) -> list[BattleReplayShip]:
        out: list[BattleReplayShip] = []
        battle_attrs = parsed.get("battle_attrs") or {}
        for side, key in (("attacker", "attacker_ship_node"), ("defender", "defender_ship_node")):
            ship_node = parsed.get(key)
            attrs: dict[str, Any] = {}
            if isinstance(ship_node, dict):
                node_attrs = ship_node.get("attributes")
                if isinstance(node_attrs, dict):
                    attrs = node_attrs
            else:
                battle_id = self._as_int(battle_attrs.get("BattleId"))
                logger.warning(
                    "event=missing_ship_xml side=%s battle_replay_id=%s battle_id=%s",
                    side,
                    battle_replay_id,
                    battle_id,
                )

            # Fallback: algunos replays no incluyen la nave del defensor en XML.
            default_ship_id = (
                self._as_int(battle_attrs.get("AttackingShipId"))
                if side == "attacker"
                else self._as_int(battle_attrs.get("DefendingShipId"))
            )
            out.append(
                BattleReplayShip(
                    battle_replay_id=battle_replay_id,
                    side=side,
                    ship_id=self._as_int(attrs.get("ShipId")) or default_ship_id,
                    ship_design_id=self._as_int(attrs.get("ShipDesignId")),
                    ship_name=self._as_text(self._normalize_text(attrs.get("ShipName")), 255),
                    ship_level=self._as_int(attrs.get("ShipLevel")),
                    power_score=self._as_int(attrs.get("PowerScore")),
                    hp=self._as_float(attrs.get("Hp")),
                    ship_status=self._as_text(attrs.get("ShipStatus"), 64),
                    ship_attributes_json=attrs if attrs else {"missing_ship_xml": True},
                )
            )
        return out

    def _build_room_rows_for_replay(self, battle_replay_id: int, parsed: dict[str, Any]) -> list[BattleReplayRoom]:
        out: list[BattleReplayRoom] = []
        for side, key in (("attacker", "attacker_ship_node"), ("defender", "defender_ship_node")):
            ship_node = parsed.get(key)
            if not isinstance(ship_node, dict):
                continue
            for room_node in self._extract_children_by_path(ship_node, ["Rooms", "Room"]):
                attrs = room_node.get("attributes")
                if not isinstance(attrs, dict):
                    continue
                attrs = dict(attrs)
                nested_attrs = self._flatten_node_attributes(room_node)
                for key_name, value in nested_attrs.items():
                    if key_name not in attrs:
                        attrs[key_name] = value
                attrs = self._normalize_room_attributes(attrs)
                out.append(
                    BattleReplayRoom(
                        battle_replay_id=battle_replay_id,
                        side=side,
                        room_id=self._as_int(attrs.get("RoomId")),
                        room_design_id=self._as_int(attrs.get("RoomDesignId")),
                        ship_id=self._as_int(attrs.get("ShipId")),
                        row=self._as_int(attrs.get("Row")),
                        column=self._as_int(attrs.get("Column")),
                        room_status=self._as_text(attrs.get("RoomStatus"), 64),
                        room_attributes_json=attrs,
                    )
                )
        return out

    def _build_character_rows_for_replay(
        self, battle_replay_id: int, parsed: dict[str, Any]
    ) -> list[BattleReplayCharacter]:
        out: list[BattleReplayCharacter] = []
        for side, key in (("attacker", "attacker_ship_node"), ("defender", "defender_ship_node")):
            ship_node = parsed.get(key)
            if not isinstance(ship_node, dict):
                continue
            for char_node in self._extract_children_by_path(ship_node, ["Characters", "Character"]):
                attrs = char_node.get("attributes")
                if not isinstance(attrs, dict):
                    continue
                attrs = dict(attrs)
                nested_attrs = self._flatten_node_attributes(char_node)
                for key_name, value in nested_attrs.items():
                    if key_name not in attrs:
                        attrs[key_name] = value
                attrs = self._normalize_character_attributes(attrs)
                out.append(
                    BattleReplayCharacter(
                        battle_replay_id=battle_replay_id,
                        side=side,
                        character_id=self._as_int(attrs.get("CharacterId")),
                        ship_id=self._as_int(attrs.get("ShipId")),
                        character_design_id=self._as_int(attrs.get("CharacterDesignId")),
                        character_name=self._as_text(self._normalize_text(attrs.get("CharacterName")), 255),
                        level=self._as_int(attrs.get("Level")),
                        xp=self._as_int(attrs.get("Xp")),
                        character_attributes_json=attrs,
                    )
                )
        return out

    def _flatten_node_attributes(self, node: dict[str, Any], prefix: str = "") -> dict[str, Any]:
        out: dict[str, Any] = {}
        children = node.get("children")
        if not isinstance(children, list):
            return out
        tag_counts: dict[str, int] = {}
        for child in children:
            if not isinstance(child, dict):
                continue
            tag = child.get("tag")
            tag_text = str(tag) if tag else "Child"
            tag_counts[tag_text] = tag_counts.get(tag_text, 0) + 1

        tag_seen: dict[str, int] = {}
        for child in children:
            if not isinstance(child, dict):
                continue
            tag = child.get("tag")
            tag_text = str(tag) if tag else "Child"
            tag_seen[tag_text] = tag_seen.get(tag_text, 0) + 1
            if tag_counts.get(tag_text, 0) > 1:
                tag_text = f"{tag_text}[{tag_seen[tag_text] - 1}]"
            next_prefix = f"{prefix}.{tag_text}" if prefix else tag_text
            attrs = child.get("attributes")
            if isinstance(attrs, dict):
                for key, value in attrs.items():
                    full_key = f"{next_prefix}.{key}"
                    if full_key not in out:
                        out[full_key] = value
            nested = self._flatten_node_attributes(child, next_prefix)
            for key, value in nested.items():
                if key not in out:
                    out[key] = value
        return out

    def _normalize_room_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        room_actions: dict[int, dict[str, Any]] = {}
        to_remove: list[str] = []
        pattern = re.compile(r"^RoomActions\.RoomAction\[(\d+)\]\.(.+)$")
        for key, value in attrs.items():
            match = pattern.match(str(key))
            if not match:
                continue
            idx = int(match.group(1))
            field = match.group(2)
            if idx not in room_actions:
                room_actions[idx] = {}
            room_actions[idx][field] = value
            to_remove.append(key)

        if room_actions:
            normalized = []
            for idx in sorted(room_actions.keys()):
                payload = room_actions[idx]
                action_index = payload.get("RoomActionIndex")
                normalized.append(
                    {
                        "index": action_index if action_index is not None else idx,
                        "condition_type_id": payload.get("ConditionTypeId"),
                        "action_type_id": payload.get("ActionTypeId"),
                        "room_action_id": payload.get("RoomActionId"),
                    }
                )
            cleaned = dict(attrs)
            for key in to_remove:
                cleaned.pop(key, None)
            cleaned["RoomActionsNormalized"] = normalized
            return cleaned

        return attrs

    def _normalize_character_attributes(self, attrs: dict[str, Any]) -> dict[str, Any]:
        character_actions: dict[int, dict[str, Any]] = {}
        character_items: dict[int, dict[str, Any]] = {}
        action_pattern = re.compile(r"^CharacterActions\.CharacterAction\[(\d+)\]\.(.+)$")
        item_pattern = re.compile(r"^Items\.Item\[(\d+)\]\.(.+)$")

        for key, value in attrs.items():
            key_text = str(key)
            action_match = action_pattern.match(key_text)
            if action_match:
                idx = int(action_match.group(1))
                field = action_match.group(2)
                character_actions.setdefault(idx, {})[field] = value
                continue
            item_match = item_pattern.match(key_text)
            if item_match:
                idx = int(item_match.group(1))
                field = item_match.group(2)
                character_items.setdefault(idx, {})[field] = value

        if not character_actions and not character_items:
            return attrs

        cleaned = dict(attrs)
        if character_actions:
            cleaned["CharacterActionsNormalized"] = [
                {
                    "index": payload.get("CharacterActionIndex", idx),
                    "condition_type_id": payload.get("ConditionTypeId"),
                    "action_type_id": payload.get("ActionTypeId"),
                    "character_action_id": payload.get("CharacterActionId"),
                }
                for idx, payload in sorted(character_actions.items())
            ]
        if character_items:
            cleaned["CharacterItemsNormalized"] = [
                {
                    "index": idx,
                    "item_id": payload.get("ItemId"),
                    "item_design_id": payload.get("ItemDesignId"),
                    "quantity": payload.get("Quantity"),
                    "is_new": payload.get("IsNew"),
                    "skin_key": payload.get("SkinKey"),
                    "bonus_enhancement_type": payload.get("BonusEnhancementType"),
                    "bonus_enhancement_value": payload.get("BonusEnhancementValue"),
                }
                for idx, payload in sorted(character_items.items())
            ]
        return cleaned

    def _build_command_rows_for_replay(self, battle_replay_id: int, parsed: dict[str, Any]) -> list[BattleReplayCommand]:
        out: list[BattleReplayCommand] = []
        commands_node = parsed.get("commands_node")
        if not isinstance(commands_node, dict):
            return out

        command_nodes = self._extract_children_by_path(commands_node, ["Commands", None])
        if not command_nodes:
            return out

        for idx, command_node in enumerate(command_nodes):
            attrs = command_node.get("attributes")
            if not isinstance(attrs, dict):
                attrs = {}
            out.append(
                BattleReplayCommand(
                    battle_replay_id=battle_replay_id,
                    command_order=idx,
                    command_tag=self._as_text(command_node.get("tag"), 64),
                    user_id=self._as_int(attrs.get("UserId")),
                    ship_id=self._as_int(attrs.get("ShipId")),
                    room_id=self._as_int(attrs.get("RoomId")),
                    character_id=self._as_int(attrs.get("CharacterId")),
                    command_attributes_json=attrs,
                )
            )
        return out

    def _extract_children_by_path(self, node: dict[str, Any], path: list[str | None]) -> list[dict[str, Any]]:
        current: list[dict[str, Any]] = [node]
        for expected_tag in path:
            next_nodes: list[dict[str, Any]] = []
            for item in current:
                children = item.get("children")
                if not isinstance(children, list):
                    continue
                for child in children:
                    if not isinstance(child, dict):
                        continue
                    if expected_tag is None or child.get("tag") == expected_tag:
                        next_nodes.append(child)
            current = next_nodes
            if not current:
                break
        return current

    def _persist_rows_one_by_one(self, db, rows: list[Any]) -> None:
        for row in rows:
            db.add(row)
            db.flush()

    def _sync_design_catalogs_from_saved_rows(self, db, rows: list[ApiFlowEvent]) -> int:
        total_updated = 0
        for row in rows:
            if not row.path or not row.path.startswith("/DesignService/ListAllStaticDesigns2"):
                continue
            parsed_ship_designs = self._extract_ship_designs_from_payload(row.response_body_preview)
            parsed_room_designs = self._extract_room_designs_from_payload(row.response_body_preview)
            parsed_character_designs = self._extract_character_designs_from_payload(row.response_body_preview)
            if not parsed_ship_designs and not parsed_room_designs and not parsed_character_designs:
                continue
            total_updated += self._upsert_ship_designs(db, parsed_ship_designs)
            total_updated += self._upsert_room_designs(db, parsed_room_designs)
            total_updated += self._upsert_character_designs(db, parsed_character_designs)
        return total_updated

    def _extract_ship_designs_from_payload(self, response_body_preview: str | None) -> list[dict[str, Any]]:
        xml_text = self._decode_design_payload_to_xml(response_body_preview)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        out: list[dict[str, Any]] = []
        for node in root.findall(".//ShipDesign"):
            attrs = dict(node.attrib or {})
            ship_design_id = self._as_int(attrs.get("ShipDesignId"))
            if ship_design_id is None:
                continue
            name_en = self._as_text(self._normalize_text(attrs.get("ShipDesignName")), 255)
            name_es = self._as_text(self._normalize_text(self._pick_design_name_es(attrs, "ShipDesignName")), 255)
            out.append(
                {
                    "ship_design_id": ship_design_id,
                    "name": name_en,
                    "name_es": name_es,
                    "description": self._as_text(self._normalize_text(attrs.get("ShipDescription")), 4096),
                    "class_type": self._as_text(attrs.get("ShipType"), 100),
                    "stats": {
                        "ShipLevel": attrs.get("ShipLevel"),
                        "Hp": attrs.get("Hp"),
                        "Rows": attrs.get("Rows"),
                        "Columns": attrs.get("Columns"),
                    },
                    "raw_data": attrs,
                }
            )
        return out

    def _extract_room_designs_from_payload(self, response_body_preview: str | None) -> list[dict[str, Any]]:
        xml_text = self._decode_design_payload_to_xml(response_body_preview)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        out: list[dict[str, Any]] = []
        for node in root.findall(".//RoomDesign"):
            attrs = dict(node.attrib or {})
            room_design_id = self._as_int(attrs.get("RoomDesignId"))
            if room_design_id is None:
                continue
            name_en = self._as_text(self._normalize_text(attrs.get("RoomName")), 255)
            name_es = self._as_text(self._normalize_text(self._pick_design_name_es(attrs, "RoomName")), 255)
            out.append(
                {
                    "room_design_id": room_design_id,
                    "name": name_en,
                    "name_es": name_es,
                    "description": self._as_text(self._normalize_text(attrs.get("RoomDescription")), 4096),
                    "room_type": self._as_text(attrs.get("RoomType"), 100),
                    "stats": {
                        "MinShipLevel": attrs.get("MinShipLevel"),
                        "Capacity": attrs.get("Capacity"),
                        "PowerUse": attrs.get("PowerUse"),
                    },
                    "raw_data": attrs,
                }
            )
        return out

    def _extract_character_designs_from_payload(self, response_body_preview: str | None) -> list[dict[str, Any]]:
        xml_text = self._decode_design_payload_to_xml(response_body_preview)
        if not xml_text:
            return []

        try:
            root = ET.fromstring(xml_text)
        except Exception:
            return []

        out: list[dict[str, Any]] = []
        for node in root.findall(".//CharacterDesign"):
            attrs = dict(node.attrib or {})
            character_design_id = self._as_int(attrs.get("CharacterDesignId"))
            if character_design_id is None:
                continue
            name_en = self._as_text(self._normalize_text(attrs.get("CharacterDesignName")), 255)
            name_es = self._as_text(self._normalize_text(self._pick_design_name_es(attrs, "CharacterDesignName")), 255)
            out.append(
                {
                    "crew_design_id": character_design_id,
                    "name": name_en,
                    "name_es": name_es,
                    "description": self._as_text(self._normalize_text(attrs.get("CharacterDesignDescription")), 4096),
                    "race": self._as_text(attrs.get("RaceType"), 100),
                    "role": self._as_text(attrs.get("CharacterType"), 100),
                    "stats": {
                        "Hp": attrs.get("Hp"),
                        "Attack": attrs.get("Attack"),
                        "FireResistance": attrs.get("FireResistance"),
                    },
                    "raw_data": attrs,
                }
            )
        return out

    def _decode_design_payload_to_xml(self, response_body_preview: str | None) -> str | None:
        text_value = self._as_full_text(response_body_preview)
        if not text_value:
            return None
        stripped = text_value.strip()
        if stripped.startswith("<"):
            return stripped

        # Some captures may line-wrap base64 content; normalize internal whitespace.
        normalized_base64 = "".join(stripped.split())
        try:
            raw = base64.b64decode(normalized_base64, validate=True)
        except (binascii.Error, ValueError):
            return None

        if raw.startswith(b"\x1f\x8b"):
            try:
                decoded = gzip.decompress(raw)
            except Exception:
                return None
        else:
            decoded = raw

        try:
            xml_text = decoded.decode("utf-8", errors="replace").strip()
            if xml_text.startswith("<"):
                return xml_text
        except Exception:
            return None
        return None

    def _upsert_ship_designs(self, db, designs: list[dict[str, Any]]) -> int:
        if not designs:
            return 0
        target_ids = [int(item["ship_design_id"]) for item in designs]
        existing_rows = (
            db.query(ShipDesign)
            .filter(ShipDesign.ship_design_id.in_(target_ids))
            .all()
        )
        existing_by_id = {int(row.ship_design_id): row for row in existing_rows if row.ship_design_id is not None}

        updated = 0
        for item in designs:
            design_id = int(item["ship_design_id"])
            row = existing_by_id.get(design_id)
            if row is None:
                db.add(
                    ShipDesign(
                        ship_design_id=design_id,
                        name=item.get("name"),
                        name_es=item.get("name_es"),
                        description=item.get("description"),
                        class_type=item.get("class_type"),
                        stats=item.get("stats"),
                        raw_data=item.get("raw_data"),
                    )
                )
                updated += 1
                continue

            row.name = item.get("name")
            row.name_es = item.get("name_es")
            row.description = item.get("description")
            row.class_type = item.get("class_type")
            row.stats = item.get("stats")
            row.raw_data = item.get("raw_data")
            updated += 1

        db.flush()
        return updated

    def _upsert_room_designs(self, db, designs: list[dict[str, Any]]) -> int:
        if not designs:
            return 0
        target_ids = [int(item["room_design_id"]) for item in designs]
        existing_rows = (
            db.query(RoomDesign)
            .filter(RoomDesign.room_design_id.in_(target_ids))
            .all()
        )
        existing_by_id = {int(row.room_design_id): row for row in existing_rows if row.room_design_id is not None}

        updated = 0
        for item in designs:
            design_id = int(item["room_design_id"])
            row = existing_by_id.get(design_id)
            if row is None:
                db.add(
                    RoomDesign(
                        room_design_id=design_id,
                        name=item.get("name"),
                        name_es=item.get("name_es"),
                        description=item.get("description"),
                        room_type=item.get("room_type"),
                        stats=item.get("stats"),
                        raw_data=item.get("raw_data"),
                    )
                )
                updated += 1
                continue

            row.name = item.get("name")
            row.name_es = item.get("name_es")
            row.description = item.get("description")
            row.room_type = item.get("room_type")
            row.stats = item.get("stats")
            row.raw_data = item.get("raw_data")
            updated += 1

        db.flush()
        return updated

    def _upsert_character_designs(self, db, designs: list[dict[str, Any]]) -> int:
        if not designs:
            return 0
        target_ids = [int(item["crew_design_id"]) for item in designs]
        existing_rows = (
            db.query(CrewDesign)
            .filter(CrewDesign.crew_design_id.in_(target_ids))
            .all()
        )
        existing_by_id = {int(row.crew_design_id): row for row in existing_rows if row.crew_design_id is not None}

        updated = 0
        for item in designs:
            design_id = int(item["crew_design_id"])
            row = existing_by_id.get(design_id)
            if row is None:
                db.add(
                    CrewDesign(
                        crew_design_id=design_id,
                        name=item.get("name"),
                        name_es=item.get("name_es"),
                        description=item.get("description"),
                        race=item.get("race"),
                        role=item.get("role"),
                        stats=item.get("stats"),
                        raw_data=item.get("raw_data"),
                    )
                )
                updated += 1
                continue

            row.name = item.get("name")
            row.name_es = item.get("name_es")
            row.description = item.get("description")
            row.race = item.get("race")
            row.role = item.get("role")
            row.stats = item.get("stats")
            row.raw_data = item.get("raw_data")
            updated += 1

        db.flush()
        return updated

    def _pair_key(self, attacker_user_id: Any, defender_user_id: Any) -> tuple[int, int] | None:
        attacker = self._as_int(attacker_user_id)
        defender = self._as_int(defender_user_id)
        if attacker is None or defender is None:
            return None
        if attacker <= 0 or defender <= 0:
            return None
        if attacker == defender:
            return None
        return (attacker, defender) if attacker < defender else (defender, attacker)

    def _winner_user_id(self, row: BattleReplayNormalized) -> int | None:
        outcome = str(row.outcome_type or "").strip().lower()
        attacker_id = self._as_int(row.attacker_user_id)
        defender_id = self._as_int(row.defender_user_id)
        if outcome == "attacker won":
            return attacker_id
        if outcome == "defender won":
            return defender_id
        return None

    def _record_matchup_log_for_rows(self, db, replay_rows: list[BattleReplayNormalized]) -> dict[str, Any]:
        candidates: list[tuple[tuple[int, int], int, BattleReplayNormalized]] = []
        affected_pairs: set[tuple[int, int]] = set()
        for row in replay_rows:
            pair = self._pair_key(row.attacker_user_id, row.defender_user_id)
            battle_id = self._as_int(row.battle_id)
            if pair is None or battle_id is None:
                continue
            affected_pairs.add(pair)
            candidates.append((pair, battle_id, row))

        if not candidates:
            return {"inserted_logs": 0, "affected_pairs": affected_pairs}

        existing_keys: set[tuple[int, int, int]] = set()
        pair_filters = [
            and_(
                PlayerMatchupLog.player_low_user_id == low_id,
                PlayerMatchupLog.player_high_user_id == high_id,
            )
            for low_id, high_id in affected_pairs
        ]
        if pair_filters:
            existing_rows = (
                db.query(
                    PlayerMatchupLog.player_low_user_id,
                    PlayerMatchupLog.player_high_user_id,
                    PlayerMatchupLog.battle_id,
                )
                .filter(or_(*pair_filters))
                .all()
            )
            existing_keys = {
                (
                    int(row.player_low_user_id),
                    int(row.player_high_user_id),
                    int(row.battle_id),
                )
                for row in existing_rows
                if row.battle_id is not None
            }

        inserted_logs = 0
        for pair, battle_id, row in candidates:
            key = (pair[0], pair[1], int(battle_id))
            if key in existing_keys:
                continue
            db.add(
                PlayerMatchupLog(
                    player_low_user_id=pair[0],
                    player_high_user_id=pair[1],
                    battle_id=battle_id,
                    winner_user_id=self._winner_user_id(row),
                    outcome_type=self._as_text(row.outcome_type, 64),
                    captured_at=row.captured_at,
                    source_battle_replay_id=row.id,
                    source_api_flow_event_id=row.api_flow_event_id,
                )
            )
            existing_keys.add(key)
            inserted_logs += 1

        if inserted_logs:
            db.flush()
            logger.info(
                "event=matchup_log_inserted inserted_logs=%s affected_pairs=%s",
                inserted_logs,
                len(affected_pairs),
            )
        return {"inserted_logs": inserted_logs, "affected_pairs": affected_pairs}

    def _recompute_matchup_stats_for_pairs(self, db, pairs: set[tuple[int, int]]) -> int:
        if not pairs:
            return 0

        pair_filters = [
            and_(
                PlayerMatchupStat.player_low_user_id == low_id,
                PlayerMatchupStat.player_high_user_id == high_id,
            )
            for low_id, high_id in pairs
        ]
        existing_stats_rows = (
            db.query(PlayerMatchupStat).filter(or_(*pair_filters)).all()
            if pair_filters
            else []
        )
        stats_by_pair = {
            (int(row.player_low_user_id), int(row.player_high_user_id)): row
            for row in existing_stats_rows
        }

        recomputed = 0
        for low_id, high_id in sorted(pairs):
            logs = (
                db.query(PlayerMatchupLog)
                .filter(
                    PlayerMatchupLog.player_low_user_id == low_id,
                    PlayerMatchupLog.player_high_user_id == high_id,
                )
                .order_by(PlayerMatchupLog.captured_at.desc(), PlayerMatchupLog.id.desc())
                .all()
            )
            existing_stat = stats_by_pair.get((low_id, high_id))
            if not logs:
                if existing_stat is not None:
                    db.delete(existing_stat)
                    recomputed += 1
                continue

            low_wins = 0
            high_wins = 0
            unknown_results = 0
            for log_row in logs:
                winner_id = self._as_int(log_row.winner_user_id)
                if winner_id == low_id:
                    low_wins += 1
                elif winner_id == high_id:
                    high_wins += 1
                else:
                    unknown_results += 1

            latest_replay = (
                db.query(BattleReplayNormalized)
                .filter(
                    or_(
                        and_(
                            BattleReplayNormalized.attacker_user_id == low_id,
                            BattleReplayNormalized.defender_user_id == high_id,
                        ),
                        and_(
                            BattleReplayNormalized.attacker_user_id == high_id,
                            BattleReplayNormalized.defender_user_id == low_id,
                        ),
                    )
                )
                .order_by(BattleReplayNormalized.captured_at.desc(), BattleReplayNormalized.id.desc())
                .first()
            )
            low_name = existing_stat.player_low_name if existing_stat is not None else None
            high_name = existing_stat.player_high_name if existing_stat is not None else None
            if latest_replay is not None:
                if self._as_int(latest_replay.attacker_user_id) == low_id:
                    low_name = latest_replay.attacker_name or low_name
                    high_name = latest_replay.defender_name or high_name
                else:
                    low_name = latest_replay.defender_name or low_name
                    high_name = latest_replay.attacker_name or high_name

            latest_log = logs[0]
            payload = {
                "player_low_name": self._as_text(self._normalize_text(low_name), 255),
                "player_high_name": self._as_text(self._normalize_text(high_name), 255),
                "total_battles": len(logs),
                "player_low_wins": low_wins,
                "player_high_wins": high_wins,
                "unknown_results": unknown_results,
                "last_battle_id": latest_log.battle_id,
                "last_winner_user_id": latest_log.winner_user_id,
                "last_captured_at": latest_log.captured_at,
            }
            if existing_stat is None:
                db.add(
                    PlayerMatchupStat(
                        player_low_user_id=low_id,
                        player_high_user_id=high_id,
                        **payload,
                    )
                )
            else:
                existing_stat.player_low_name = payload["player_low_name"]
                existing_stat.player_high_name = payload["player_high_name"]
                existing_stat.total_battles = payload["total_battles"]
                existing_stat.player_low_wins = payload["player_low_wins"]
                existing_stat.player_high_wins = payload["player_high_wins"]
                existing_stat.unknown_results = payload["unknown_results"]
                existing_stat.last_battle_id = payload["last_battle_id"]
                existing_stat.last_winner_user_id = payload["last_winner_user_id"]
                existing_stat.last_captured_at = payload["last_captured_at"]
            recomputed += 1

        if recomputed:
            db.flush()
            logger.info("event=matchup_stats_recomputed pairs=%s", recomputed)
        return recomputed

    def _prune_obsolete_replays_for_pairs(self, db, pairs: set[tuple[int, int]]) -> int:
        if not pairs:
            return 0

        obsolete_event_ids: set[int] = set()
        deleted_replay_count = 0
        for low_id, high_id in sorted(pairs):
            replay_rows = (
                db.query(BattleReplayNormalized.id, BattleReplayNormalized.api_flow_event_id)
                .filter(
                    or_(
                        and_(
                            BattleReplayNormalized.attacker_user_id == low_id,
                            BattleReplayNormalized.defender_user_id == high_id,
                        ),
                        and_(
                            BattleReplayNormalized.attacker_user_id == high_id,
                            BattleReplayNormalized.defender_user_id == low_id,
                        ),
                    )
                )
                .order_by(BattleReplayNormalized.captured_at.desc(), BattleReplayNormalized.id.desc())
                .all()
            )
            if len(replay_rows) <= 1:
                continue
            obsolete_rows = replay_rows[1:]
            deleted_replay_count += len(obsolete_rows)
            for row in obsolete_rows:
                if row.api_flow_event_id is not None:
                    obsolete_event_ids.add(int(row.api_flow_event_id))

        if obsolete_event_ids:
            self._delete_events_and_normalized(db, sorted(obsolete_event_ids))
        if deleted_replay_count:
            logger.info(
                "event=matchup_prune_obsolete_replays deleted_replays=%s affected_pairs=%s",
                deleted_replay_count,
                len(pairs),
            )
        return deleted_replay_count

    def _delete_events_and_normalized(self, db, event_ids: list[int]) -> int:
        if not event_ids:
            return 0

        replay_ids = [
            row[0]
            for row in db.query(BattleReplayNormalized.id)
            .filter(BattleReplayNormalized.api_flow_event_id.in_(event_ids))
            .all()
        ]
        if replay_ids:
            db.query(BattleReplayCommand).filter(
                BattleReplayCommand.battle_replay_id.in_(replay_ids)
            ).delete(synchronize_session=False)
            db.query(BattleReplayCharacter).filter(
                BattleReplayCharacter.battle_replay_id.in_(replay_ids)
            ).delete(synchronize_session=False)
            db.query(BattleReplayRoom).filter(
                BattleReplayRoom.battle_replay_id.in_(replay_ids)
            ).delete(synchronize_session=False)
            db.query(BattleReplayShip).filter(
                BattleReplayShip.battle_replay_id.in_(replay_ids)
            ).delete(synchronize_session=False)
            db.query(BattleReplayNormalized).filter(
                BattleReplayNormalized.id.in_(replay_ids)
            ).delete(synchronize_session=False)

        deleted = (
            db.query(ApiFlowEvent)
            .filter(ApiFlowEvent.id.in_(event_ids))
            .delete(synchronize_session=False)
        )
        return int(deleted or 0)
