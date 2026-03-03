from __future__ import annotations

from app.services.api_flow_storage import ApiFlowRepository


def test_redacts_sensitive_headers() -> None:
    repo = ApiFlowRepository()
    headers = {
        "Authorization": "Bearer abc",
        "Cookie": "session=x",
        "Content-Type": "application/json",
    }
    redacted = repo._redact_headers(headers)
    assert redacted["Authorization"] == "***REDACTED***"
    assert redacted["Cookie"] == "***REDACTED***"
    assert redacted["Content-Type"] == "application/json"


def test_truncate_body_uses_config_limit() -> None:
    repo = ApiFlowRepository()
    long_body = "x" * (repo.body_max_chars + 50)
    out = repo._truncate(long_body)
    assert out is not None
    assert out.endswith("...")
    assert len(out) == repo.body_max_chars + 3


def test_parse_datetime_handles_z_suffix() -> None:
    repo = ApiFlowRepository()
    parsed = repo._parse_datetime("2026-02-20T10:00:00Z")
    assert parsed is not None
    assert parsed.isoformat().startswith("2026-02-20T10:00:00")
