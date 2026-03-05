from __future__ import annotations

import json
import logging
import os
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from typing import Any

from sqlalchemy import String, cast, or_, text

from app.core.config import settings
from app.models.database import SessionLocal, engine
from app.models.pss_models import (
    ApiFlowEvent,
    BattleReplayCharacter,
    BattleReplayCommand,
    BattleReplayNormalized,
    BattleReplayRoom,
    BattleReplayShip,
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


class ApiFlowRepository:
    def __init__(self) -> None:
        self.body_max_chars = max(128, int(settings.API_FLOW_BODY_MAX_CHARS))

    def save_events(self, events: list[dict[str, Any]]) -> int:
        if not events:
            return 0

        rows: list[ApiFlowEvent] = []
        for event in events:
            normalized = self._normalize_event(event)
            rows.append(ApiFlowEvent(**normalized))

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
            db.commit()
            return len(rows)
        except Exception:
            db.rollback()
            logger.exception("event=api_flow_save_error count=%s", len(events))
            return 0
        finally:
            db.close()

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
            deleted = db.query(BattleReplayNormalized).delete(synchronize_session=False)
            db.commit()
            return int(deleted or 0)
        except Exception:
            db.rollback()
            logger.exception("event=battle_replay_clear_error")
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

    def sync_battle_replays_from_api_flow(self, batch_size: int = 500) -> int:
        db = SessionLocal()
        inserted = 0
        try:
            last_seen_id = 0
            while True:
                candidates = (
                    db.query(ApiFlowEvent)
                    .outerjoin(
                        BattleReplayNormalized,
                        BattleReplayNormalized.api_flow_event_id == ApiFlowEvent.id,
                    )
                    .filter(BattleReplayNormalized.id.is_(None))
                    .filter(ApiFlowEvent.path.like("/BattleService/GetBattle3%"))
                    .filter(ApiFlowEvent.response_body_cleaned.isnot(None))
                    .filter(ApiFlowEvent.id > last_seen_id)
                    .order_by(ApiFlowEvent.id.asc())
                    .limit(max(1, batch_size))
                    .all()
                )
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
                db.commit()
                inserted += len(new_rows)
                return inserted
        except Exception:
            db.rollback()
            logger.exception("event=battle_replay_sync_error")
            return inserted
        finally:
            db.close()

    def backfill_response_body_cleaned(self, batch_size: int = 100) -> int:
        db = SessionLocal()
        updated = 0
        try:
            candidates = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.path.like("/BattleService/GetBattle3%"))
                .filter(
                    or_(
                        ApiFlowEvent.response_body_cleaned.is_(None),
                        ApiFlowEvent.response_body_cleaned == "",
                    )
                )
                .order_by(ApiFlowEvent.id.asc())
                .limit(max(1, batch_size))
                .all()
            )
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

    def sync_battle_replay_children(self, batch_size: int = 200) -> int:
        db = SessionLocal()
        inserted = 0
        try:
            parents = (
                db.query(BattleReplayNormalized)
                .outerjoin(
                    BattleReplayShip,
                    BattleReplayShip.battle_replay_id == BattleReplayNormalized.id,
                )
                .filter(BattleReplayShip.id.is_(None))
                .order_by(BattleReplayNormalized.id.asc())
                .limit(max(1, batch_size))
                .all()
            )
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
            "direction": str(event.get("direction") or "response")[:16],
            "method": self._as_text(event.get("method"), 16),
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
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
        normalized = "\n".join(line.rstrip() for line in normalized.split("\n")).strip()
        if not normalized:
            return None
        return normalized

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
            "attacker_name": row.attacker_name,
            "attacker_trophy": row.attacker_trophy,
            "defender_user_id": row.defender_user_id,
            "defender_name": row.defender_name,
            "defender_trophy": row.defender_trophy,
            "battle_attributes_json": row.battle_attributes_json,
            "attacker_user_attributes_json": row.attacker_user_attributes_json,
            "defender_user_attributes_json": row.defender_user_attributes_json,
        }

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
        for side, key in (("attacker", "attacker_ship_node"), ("defender", "defender_ship_node")):
            ship_node = parsed.get(key)
            if not isinstance(ship_node, dict):
                continue
            attrs = ship_node.get("attributes")
            if not isinstance(attrs, dict):
                continue
            out.append(
                BattleReplayShip(
                    battle_replay_id=battle_replay_id,
                    side=side,
                    ship_id=self._as_int(attrs.get("ShipId")),
                    ship_design_id=self._as_int(attrs.get("ShipDesignId")),
                    ship_name=self._as_text(self._normalize_text(attrs.get("ShipName")), 255),
                    ship_level=self._as_int(attrs.get("ShipLevel")),
                    power_score=self._as_int(attrs.get("PowerScore")),
                    hp=self._as_float(attrs.get("Hp")),
                    ship_status=self._as_text(attrs.get("ShipStatus"), 64),
                    ship_attributes_json=attrs,
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
