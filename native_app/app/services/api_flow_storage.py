from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, text

from app.core.config import settings
from app.models.database import SessionLocal, engine
from app.models.pss_models import ApiFlowEvent

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
            deleted = (
                db.query(ApiFlowEvent)
                .filter(ApiFlowEvent.captured_at < threshold)
                .delete(synchronize_session=False)
            )
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
                deleted = (
                    db.query(ApiFlowEvent)
                    .filter(ApiFlowEvent.id.in_(oldest_ids))
                    .delete(synchronize_session=False)
                )
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
            "response_body_preview": self._truncate(event.get("response_body_preview")),
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
