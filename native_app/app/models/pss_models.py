from sqlalchemy import Boolean, Column, DateTime, Float, Integer, JSON, String, Text, UniqueConstraint
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
    item_design_key = Column(String(100))
    item_design_name_en = Column(String(255))
    item_design_description_raw = Column(Text)
    level = Column(Integer)
    item_sub_type = Column(String(100))
    min_ship_level = Column(Integer)
    min_room_level = Column(Integer)
    market_price = Column(Integer)
    fair_price = Column(Integer)
    build_time = Column(Integer)
    build_price = Column(Integer)
    mineral_cost = Column(Integer)
    gas_cost = Column(Integer)
    manufacture_cost = Column(Integer)
    starbase_manufacture_cost = Column(Integer)
    our_price = Column(Integer)
    active_animation_id = Column(Integer)
    animation_id = Column(Integer)
    border_sprite_id = Column(Integer)
    character_design_id = Column(Integer)
    character_part_id = Column(Integer)
    character_part = Column(Text)
    circulation = Column(Integer)
    content = Column(Text)
    craft_design_id = Column(Integer)
    equip_sound_file_id = Column(Integer)
    flags = Column(Integer)
    image_sprite_id = Column(Integer)
    logo_sprite_id = Column(Integer)
    missile_design_id = Column(Integer)
    parent_item_design_id = Column(Integer)
    particle_sprite_id = Column(Integer)
    priority = Column(Integer)
    race_id = Column(Integer)
    rank = Column(Integer)
    reload_modifier = Column(Float)
    reload_time = Column(Float)
    requirement_string = Column(Text)
    room_design_id = Column(Integer)
    root_item_design_id = Column(Integer)
    situation_design_id = Column(Integer)
    sound_file_id = Column(Integer)
    training_design_id = Column(Integer)
    transaction_volume = Column(Integer)
    module_type = Column(String(100))
    module_argument = Column(Text)
    enhancement_type = Column(String(100))
    enhancement_value = Column(Float)
    drop_chance = Column(Float)
    max_count = Column(Integer)
    item_space = Column(Integer)
    required_research_design_id = Column(Integer)
    tags = Column(Text)
    ingredients = Column(JSON)
    metadata_json = Column(JSON)
    stats = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ItemIngredient(Base):
    __tablename__ = "item_ingredients"
    __table_args__ = (
        UniqueConstraint("item_design_id", "ingredient_item_design_id", name="ux_item_ingredients_item_ing"),
    )

    id = Column(Integer, primary_key=True, index=True)
    item_design_id = Column(Integer, index=True, nullable=False)
    ingredient_item_design_id = Column(Integer, index=True, nullable=False)
    quantity = Column(Integer, nullable=False)


class ItemTag(Base):
    __tablename__ = "item_tags"
    __table_args__ = (
        UniqueConstraint("item_design_id", "tag", name="ux_item_tags_item_tag"),
    )

    id = Column(Integer, primary_key=True, index=True)
    item_design_id = Column(Integer, index=True, nullable=False)
    tag = Column(String(100), index=True, nullable=False)

class ShipDesign(Base):
    __tablename__ = "ship_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    ship_design_id = Column(Integer, unique=True, index=True)
    name = Column(String(255))
    name_es = Column(String(255))
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
    name_es = Column(String(255))
    description = Column(Text)
    race = Column(String(100))
    role = Column(String(100))
    stats = Column(JSON)
    raw_data = Column(JSON)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class RoomDesign(Base):
    __tablename__ = "room_designs"
    
    id = Column(Integer, primary_key=True, index=True)
    room_design_id = Column(Integer, unique=True, index=True)
    name = Column(String(255))
    name_es = Column(String(255))
    description = Column(Text)
    room_type = Column(String(100))
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


class ImportedGameFile(Base):
    __tablename__ = "imported_game_files"

    id = Column(Integer, primary_key=True, index=True)
    source_dir = Column(String(1024))
    relative_path = Column(String(2048), index=True)
    file_name = Column(String(255), nullable=False)
    file_ext = Column(String(32))
    file_size = Column(Integer, nullable=False)
    content_hash = Column(String(64), unique=True, index=True, nullable=False)
    content_text = Column(Text, nullable=False)
    imported_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ApiFlowEvent(Base):
    __tablename__ = "api_flow_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(64), index=True, nullable=False)
    captured_at = Column(DateTime(timezone=True), index=True, server_default=func.now())
    direction = Column(String(16), nullable=False, default="response")
    method = Column(String(16))
    scheme = Column(String(16))
    host = Column(String(255), index=True)
    port = Column(Integer)
    path = Column(String(2048), index=True)
    query = Column(Text)
    url_full = Column(Text)
    status_code = Column(Integer, index=True)
    duration_ms = Column(Integer)
    request_headers_json = Column(JSON)
    response_headers_json = Column(JSON)
    request_body_preview = Column(Text)
    response_body_preview = Column(Text)
    response_body_cleaned = Column(Text)
    request_size_bytes = Column(Integer)
    response_size_bytes = Column(Integer)
    content_type_request = Column(String(255))
    content_type_response = Column(String(255))
    tls = Column(Boolean, default=False)
    error_text = Column(String(2048))
    game_process_hint = Column(String(255))
    flow_hash = Column(String(100), index=True)


class BattleReplayNormalized(Base):
    __tablename__ = "battle_replays_normalized"

    id = Column(Integer, primary_key=True, index=True)
    api_flow_event_id = Column(Integer, unique=True, index=True, nullable=False)
    battle_id = Column(Integer, index=True, nullable=False)
    captured_at = Column(DateTime(timezone=True), index=True)

    attacking_ship_id = Column(Integer, index=True)
    defending_ship_id = Column(Integer, index=True)
    outcome_type = Column(String(64), index=True)
    client_outcome_type = Column(String(64), index=True)

    win_trophy_result = Column(Integer)
    win_minerals_result = Column(Integer)
    win_gas_result = Column(Integer)
    lose_trophy_result = Column(Integer)
    lose_minerals_result = Column(Integer)
    lose_gas_result = Column(Integer)

    battle_end_frame = Column(Integer)
    client_end_frame = Column(Integer)

    attacker_user_id = Column(Integer, index=True)
    attacker_name = Column(String(255), index=True)
    attacker_trophy = Column(Integer)

    defender_user_id = Column(Integer, index=True)
    defender_name = Column(String(255), index=True)
    defender_trophy = Column(Integer)

    battle_attributes_json = Column(JSON)
    attacker_user_attributes_json = Column(JSON)
    defender_user_attributes_json = Column(JSON)


class BattleReplayShip(Base):
    __tablename__ = "battle_replay_ships"

    id = Column(Integer, primary_key=True, index=True)
    battle_replay_id = Column(Integer, index=True, nullable=False)
    side = Column(String(16), index=True, nullable=False)
    ship_id = Column(Integer, index=True)
    ship_design_id = Column(Integer)
    ship_name = Column(String(255), index=True)
    ship_level = Column(Integer)
    power_score = Column(Integer)
    hp = Column(Float)
    ship_status = Column(String(64), index=True)
    ship_attributes_json = Column(JSON)


class BattleReplayRoom(Base):
    __tablename__ = "battle_replay_rooms"

    id = Column(Integer, primary_key=True, index=True)
    battle_replay_id = Column(Integer, index=True, nullable=False)
    side = Column(String(16), index=True, nullable=False)
    room_id = Column(Integer, index=True)
    room_design_id = Column(Integer, index=True)
    ship_id = Column(Integer, index=True)
    row = Column(Integer)
    column = Column(Integer)
    room_status = Column(String(64), index=True)
    room_attributes_json = Column(JSON)


class BattleReplayCharacter(Base):
    __tablename__ = "battle_replay_characters"

    id = Column(Integer, primary_key=True, index=True)
    battle_replay_id = Column(Integer, index=True, nullable=False)
    side = Column(String(16), index=True, nullable=False)
    character_id = Column(Integer, index=True)
    ship_id = Column(Integer, index=True)
    character_design_id = Column(Integer, index=True)
    character_name = Column(String(255), index=True)
    level = Column(Integer)
    xp = Column(Integer)
    character_attributes_json = Column(JSON)


class BattleReplayCommand(Base):
    __tablename__ = "battle_replay_commands"

    id = Column(Integer, primary_key=True, index=True)
    battle_replay_id = Column(Integer, index=True, nullable=False)
    command_order = Column(Integer, nullable=False)
    command_tag = Column(String(64), index=True)
    user_id = Column(Integer, index=True)
    ship_id = Column(Integer, index=True)
    room_id = Column(Integer, index=True)
    character_id = Column(Integer, index=True)
    command_attributes_json = Column(JSON)
