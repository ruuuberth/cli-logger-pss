import asyncio
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.endpoints.crews import get_crew_designs
from app.api.v1.endpoints.items import get_item_designs
from app.api.v1.endpoints.ships import get_ship_designs
from app.models.database import Base
from app.models.pss_models import CrewDesign, ItemDesign, ShipDesign


def _seed_data(session):
    now = datetime.now(timezone.utc)
    session.add(
        ItemDesign(
            item_design_id=1001,
            name="Test Item",
            description="item desc",
            rarity="Common",
            item_type="Equipment",
            stats={"attack": 1},
            raw_data={"source": "test"},
            created_at=now,
        )
    )
    session.add(
        ShipDesign(
            ship_design_id=2001,
            name="Test Ship",
            description="ship desc",
            class_type="Frigate",
            stats={"health": 10},
            raw_data={"source": "test"},
            created_at=now,
        )
    )
    session.add(
        CrewDesign(
            crew_design_id=3001,
            name="Test Crew",
            description="crew desc",
            race="Human",
            role="Pilot",
            stats={"speed": 3},
            raw_data={"source": "test"},
            created_at=now,
        )
    )
    session.commit()


def _build_test_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as session:
        _seed_data(session)

    return TestingSessionLocal()


def test_items_designs_endpoint_returns_rows():
    db = _build_test_session()
    try:
        payload = asyncio.run(get_item_designs(refresh=False, ttl_seconds=None, db=db))
        assert payload["count"] > 0
        assert isinstance(payload["data"], list)
        assert {"id", "name", "rarity", "item_type", "stats"}.issubset(payload["data"][0].keys())
    finally:
        db.close()


def test_ships_designs_endpoint_returns_rows():
    db = _build_test_session()
    try:
        payload = asyncio.run(get_ship_designs(refresh=False, ttl_seconds=None, db=db))
        assert payload["count"] > 0
        assert isinstance(payload["data"], list)
        assert {"id", "name", "class_type", "stats"}.issubset(payload["data"][0].keys())
    finally:
        db.close()


def test_crews_designs_endpoint_returns_rows():
    db = _build_test_session()
    try:
        payload = asyncio.run(get_crew_designs(refresh=False, ttl_seconds=None, db=db))
        assert payload["count"] > 0
        assert isinstance(payload["data"], list)
        assert {
            "id",
            "name",
            "race",
            "role",
            "stats",
            "rarity",
            "collection",
            "special_ability",
            "progression_type",
            "equipment_mask",
        }.issubset(payload["data"][0].keys())
    finally:
        db.close()
