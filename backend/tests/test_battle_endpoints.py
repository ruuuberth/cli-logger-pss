import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.battles import get_battle_report, get_stored_battle_ids
from app.models.database import Base
from app.services.pss_service import PSSAuthenticationError, PSSFeatureNotSupportedError, PSSService


def _build_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_battle_report_endpoint_returns_payload(monkeypatch):
    async def _fake_get_battle_report(
        self,
        battle_id,
        access_token=None,
        force_refresh=False,
        ttl_seconds=None,
    ):
        return {
            "battle_id": battle_id,
            "player_name": "TestUser",
            "opponent_name": "Enemy",
            "battle_type": "PVP",
            "result": "Win",
            "xml_report": "<Battle/>",
            "source": "api",
        }

    monkeypatch.setattr(PSSService, "get_battle_report", _fake_get_battle_report)

    db = _build_test_session()
    try:
        payload = asyncio.run(get_battle_report(battle_id=123, access_token="token", db=db))
        assert payload["data"]["battle_id"] == 123
        assert payload["data"]["player_name"] == "TestUser"
        assert payload["data"]["source"] == "api"
    finally:
        db.close()


def test_battle_report_endpoint_returns_401_when_auth_fails(monkeypatch):
    async def _raise_auth_error(
        self,
        battle_id,
        access_token=None,
        force_refresh=False,
        ttl_seconds=None,
    ):
        raise PSSAuthenticationError("token required")

    monkeypatch.setattr(PSSService, "get_battle_report", _raise_auth_error)

    db = _build_test_session()
    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(get_battle_report(battle_id=123, db=db))
        assert getattr(exc_info.value, "status_code", None) == 401
    finally:
        db.close()


def test_battle_report_endpoint_returns_501_when_not_supported(monkeypatch):
    async def _raise_not_supported(
        self,
        battle_id,
        access_token=None,
        force_refresh=False,
        ttl_seconds=None,
    ):
        raise PSSFeatureNotSupportedError("not supported")

    monkeypatch.setattr(PSSService, "get_battle_report", _raise_not_supported)

    db = _build_test_session()
    try:
        with pytest.raises(Exception) as exc_info:
            asyncio.run(get_battle_report(battle_id=123, access_token="token", db=db))
        assert getattr(exc_info.value, "status_code", None) == 501
    finally:
        db.close()


def test_stored_battles_endpoint_returns_payload(monkeypatch):
    def _fake_list_stored_battle_ids(self, limit=200, offset=0, search=None, has_report=None):
        return {
            "data": [
                {
                    "battle_id": 2762417,
                    "player_name": "TestUser",
                    "opponent_name": "Enemy",
                    "has_report": True,
                }
            ],
            "count": 1,
            "total": 1,
            "limit": limit,
            "offset": offset,
        }

    monkeypatch.setattr(PSSService, "list_stored_battle_ids", _fake_list_stored_battle_ids)

    db = _build_test_session()
    try:
        payload = asyncio.run(
            get_stored_battle_ids(limit=100, offset=0, search="Test", has_report=True, db=db)
        )
        assert payload["count"] == 1
        assert payload["data"][0]["battle_id"] == 2762417
        assert payload["data"][0]["has_report"] is True
    finally:
        db.close()
