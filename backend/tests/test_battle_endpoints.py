import asyncio

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.battles import get_user_recent_battles
from app.models.database import Base
from app.services.pss_service import PSSService


def _build_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestingSessionLocal()


def test_recent_battles_endpoint_returns_payload(monkeypatch):
    async def _fake_get_recent_battles(self, username, limit):
        return [
            {
                "id": "battle-1",
                "player_name": username,
                "result": "Win",
                "opponent_name": "Enemy",
                "battle_type": "PVP",
                "trophy_change": 12,
                "created_at": "2026-01-01T00:00:00+00:00",
                "raw_data": {},
            }
        ][:limit]

    monkeypatch.setattr(PSSService, "get_user_recent_battles", _fake_get_recent_battles)

    db = _build_test_session()
    try:
        payload = asyncio.run(get_user_recent_battles(username="TestUser", limit=10, db=db))
        assert payload["username"] == "TestUser"
        assert payload["count"] == 1
        assert payload["data"][0]["player_name"] == "TestUser"
        assert payload["data"][0]["result"] == "Win"
    finally:
        db.close()
