import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.auth import (
    EmailLoginRequest,
    RefreshLoginRequest,
    login_with_email_password,
    login_with_refresh_token,
)
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


def test_email_login_endpoint_returns_tokens(monkeypatch):
    async def _fake_login(self, email, password, device_key=None):
        return {
            "access_token": "test-access",
            "refresh_token": "test-refresh",
            "device_key": device_key or "generated-device",
            "user_id": 1,
            "username": "TestUser",
        }

    monkeypatch.setattr(PSSService, "login_with_email_password", _fake_login)

    db = _build_test_session()
    try:
        payload = EmailLoginRequest(email="user@example.com", password="secret")
        response = asyncio.run(login_with_email_password(payload, db=db))
        assert response["data"]["access_token"] == "test-access"
        assert response["data"]["refresh_token"] == "test-refresh"
    finally:
        db.close()


def test_email_login_endpoint_returns_401_on_auth_error(monkeypatch):
    async def _fake_login(self, email, password, device_key=None):
        raise PSSAuthenticationError("invalid credentials")

    monkeypatch.setattr(PSSService, "login_with_email_password", _fake_login)

    db = _build_test_session()
    try:
        payload = EmailLoginRequest(email="user@example.com", password="secret")
        with pytest.raises(Exception) as exc_info:
            asyncio.run(login_with_email_password(payload, db=db))
        assert getattr(exc_info.value, "status_code", None) == 401
    finally:
        db.close()


def test_email_login_request_validates_password_required():
    with pytest.raises(ValidationError):
        EmailLoginRequest(email="user@example.com", password="")


def test_email_login_endpoint_returns_501_when_checksum_missing(monkeypatch):
    async def _fake_login(self, email, password, device_key=None):
        raise PSSFeatureNotSupportedError("missing checksum")

    monkeypatch.setattr(PSSService, "login_with_email_password", _fake_login)

    db = _build_test_session()
    try:
        payload = EmailLoginRequest(email="user@example.com", password="secret")
        with pytest.raises(Exception) as exc_info:
            asyncio.run(login_with_email_password(payload, db=db))
        assert getattr(exc_info.value, "status_code", None) == 501
    finally:
        db.close()


def test_refresh_login_endpoint_returns_tokens(monkeypatch):
    async def _fake_refresh(self, refresh_token, device_key=None):
        return {
            "access_token": "ref-access",
            "refresh_token": refresh_token,
            "device_key": device_key or "generated-device",
            "user_id": 2,
            "username": "RefreshUser",
        }

    monkeypatch.setattr(PSSService, "login_with_refresh_token", _fake_refresh)

    db = _build_test_session()
    try:
        payload = RefreshLoginRequest(refresh_token="refresh-123", device_key="device-1")
        response = asyncio.run(login_with_refresh_token(payload, db=db))
        assert response["data"]["access_token"] == "ref-access"
        assert response["data"]["refresh_token"] == "refresh-123"
    finally:
        db.close()


def test_refresh_login_endpoint_returns_401_on_auth_error(monkeypatch):
    async def _fake_refresh(self, refresh_token, device_key=None):
        raise PSSAuthenticationError("invalid refresh")

    monkeypatch.setattr(PSSService, "login_with_refresh_token", _fake_refresh)

    db = _build_test_session()
    try:
        payload = RefreshLoginRequest(refresh_token="refresh-123")
        with pytest.raises(Exception) as exc_info:
            asyncio.run(login_with_refresh_token(payload, db=db))
        assert getattr(exc_info.value, "status_code", None) == 401
    finally:
        db.close()


def test_refresh_login_request_validates_required_refresh_token():
    with pytest.raises(ValidationError):
        RefreshLoginRequest(refresh_token="")
