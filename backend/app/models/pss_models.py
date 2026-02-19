from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from sqlalchemy.sql import func
from app.models.database import Base

class ItemDesign(Base):
    __tablename__ = "item_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    item_design_id = Column(Integer, unique=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    rarity = Column(String(50))
    item_type = Column(String(100))
    stats = Column(JSON)
    raw_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class ShipDesign(Base):
    __tablename__ = "ship_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    ship_design_id = Column(Integer, unique=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    class_type = Column(String(100))
    stats = Column(JSON)
    raw_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class CrewDesign(Base):
    __tablename__ = "crew_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    crew_design_id = Column(Integer, unique=True, index=True)
    name = Column(String(255))
    description = Column(Text)
    race = Column(String(100))
    role = Column(String(100))
    stats = Column(JSON)
    raw_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BattleReport(Base):
    __tablename__ = "battle_reports"

    id = Column(Integer, primary_key=True, index=True)
    battle_id = Column(Integer, unique=True, index=True, nullable=False)
    player_name = Column(String(255))
    opponent_name = Column(String(255))
    battle_type = Column(String(100))
    result = Column(String(100))
    battle_start_date = Column(String(100))
    battle_end_date = Column(String(100))
    xml_report = Column(Text, nullable=False)
    summary_data = Column(JSON)
    source_endpoint = Column(String(255))
    fetched_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class BattleIndex(Base):
    __tablename__ = "battle_index"

    id = Column(Integer, primary_key=True, index=True)
    battle_id = Column(Integer, unique=True, index=True, nullable=False)
    player_name = Column(String(255))
    opponent_name = Column(String(255))
    battle_type = Column(String(100))
    result = Column(String(100))
    trophy_change = Column(String(100))
    created_at_value = Column(String(100))
    first_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    snapshot_data = Column(JSON)
