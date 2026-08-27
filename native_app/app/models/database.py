import json
import logging
from typing import Any, Optional

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

_is_sqlite_url = str(settings.DATABASE_URL).startswith("sqlite")
_sqlite_connect_args = {"timeout": 30} if _is_sqlite_url else {}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_sqlite_connect_args,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

logger = logging.getLogger(__name__)


if engine.dialect.name == "sqlite":
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, connection_record) -> None:  # pragma: no cover
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=30000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


ITEM_DESIGNS_SQLITE_COLUMNS: dict[str, str] = {
    "item_design_key": "VARCHAR(100)",
    "item_design_name_en": "VARCHAR(255)",
    "item_design_description_raw": "TEXT",
    "level": "INTEGER",
    "item_sub_type": "VARCHAR(100)",
    "min_ship_level": "INTEGER",
    "min_room_level": "INTEGER",
    "market_price": "INTEGER",
    "fair_price": "INTEGER",
    "build_time": "INTEGER",
    "build_price": "INTEGER",
    "mineral_cost": "INTEGER",
    "gas_cost": "INTEGER",
    "manufacture_cost": "INTEGER",
    "starbase_manufacture_cost": "INTEGER",
    "our_price": "INTEGER",
    "active_animation_id": "INTEGER",
    "animation_id": "INTEGER",
    "border_sprite_id": "INTEGER",
    "character_design_id": "INTEGER",
    "character_part_id": "INTEGER",
    "character_part": "TEXT",
    "circulation": "INTEGER",
    "content": "TEXT",
    "craft_design_id": "INTEGER",
    "equip_sound_file_id": "INTEGER",
    "flags": "INTEGER",
    "image_sprite_id": "INTEGER",
    "logo_sprite_id": "INTEGER",
    "missile_design_id": "INTEGER",
    "parent_item_design_id": "INTEGER",
    "particle_sprite_id": "INTEGER",
    "priority": "INTEGER",
    "race_id": "INTEGER",
    "rank": "INTEGER",
    "reload_modifier": "FLOAT",
    "reload_time": "FLOAT",
    "requirement_string": "TEXT",
    "room_design_id": "INTEGER",
    "root_item_design_id": "INTEGER",
    "situation_design_id": "INTEGER",
    "sound_file_id": "INTEGER",
    "training_design_id": "INTEGER",
    "transaction_volume": "INTEGER",
    "module_type": "VARCHAR(100)",
    "module_argument": "TEXT",
    "enhancement_type": "VARCHAR(100)",
    "enhancement_value": "FLOAT",
    "drop_chance": "FLOAT",
    "max_count": "INTEGER",
    "item_space": "INTEGER",
    "required_research_design_id": "INTEGER",
    "tags": "TEXT",
    "ingredients": "JSON",
    "metadata_json": "JSON",
}

ITEM_DESIGNS_RAW_MAP: dict[str, str] = {
    "item_design_key": "ItemDesignKey",
    "item_design_name_en": "ItemDesignNameEN",
    "item_design_description_raw": "ItemDesignDescription",
    "level": "Level",
    "item_sub_type": "ItemSubType",
    "min_ship_level": "MinShipLevel",
    "min_room_level": "MinRoomLevel",
    "market_price": "MarketPrice",
    "fair_price": "FairPrice",
    "build_time": "BuildTime",
    "build_price": "BuildPrice",
    "mineral_cost": "MineralCost",
    "gas_cost": "GasCost",
    "manufacture_cost": "ManufactureCost",
    "starbase_manufacture_cost": "StarbaseManufactureCost",
    "our_price": "OurPrice",
    "active_animation_id": "ActiveAnimationId",
    "animation_id": "AnimationId",
    "border_sprite_id": "BorderSpriteId",
    "character_design_id": "CharacterDesignId",
    "character_part_id": "CharacterPartId",
    "character_part": "CharacterPart",
    "circulation": "Circulation",
    "content": "Content",
    "craft_design_id": "CraftDesignId",
    "equip_sound_file_id": "EquipSoundFileId",
    "flags": "Flags",
    "image_sprite_id": "ImageSpriteId",
    "logo_sprite_id": "LogoSpriteId",
    "missile_design_id": "MissileDesignId",
    "parent_item_design_id": "ParentItemDesignId",
    "particle_sprite_id": "ParticleSpriteId",
    "priority": "Priority",
    "race_id": "RaceId",
    "rank": "Rank",
    "reload_modifier": "ReloadModifier",
    "reload_time": "ReloadTime",
    "requirement_string": "RequirementString",
    "room_design_id": "RoomDesignId",
    "root_item_design_id": "RootItemDesignId",
    "situation_design_id": "SituationDesignId",
    "sound_file_id": "SoundFileId",
    "training_design_id": "TrainingDesignId",
    "transaction_volume": "TransactionVolume",
    "module_type": "ModuleType",
    "module_argument": "ModuleArgument",
    "enhancement_type": "EnhancementType",
    "enhancement_value": "EnhancementValue",
    "drop_chance": "DropChance",
    "max_count": "MaxCount",
    "item_space": "ItemSpace",
    "required_research_design_id": "RequiredResearchDesignId",
    "tags": "Tags",
    "ingredients": "Ingredients",
    "metadata_json": "Metadata",
}

API_FLOW_EVENTS_SQLITE_COLUMNS: dict[str, str] = {
    # SECURITY: These columns may contain sensitive data (API keys, tokens, PII, session IDs)
    # from HTTP request/response bodies. Data is filtered by ApiFlowRepository._clean_response_body()
    # before storage, but residual sensitive data may remain.
    # TODO: Consider column-level encryption for sensitive data at rest.
    # Data retention: Configure retention policy via API_FLOW_RETENTION_DAYS setting.
    "request_body_preview": "TEXT",
    "response_body_preview": "TEXT",
    "response_body_cleaned": "TEXT",
}


def ensure_sqlite_schema() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" in tables:
            table_info = conn.exec_driver_sql("PRAGMA table_info(item_designs)").fetchall()
            existing_columns = {row[1] for row in table_info}

            for column_name, column_type in ITEM_DESIGNS_SQLITE_COLUMNS.items():
                if column_name in existing_columns:
                    continue
                conn.exec_driver_sql(f"ALTER TABLE item_designs ADD COLUMN {column_name} {column_type}")

            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS item_ingredients (
                    id INTEGER NOT NULL PRIMARY KEY,
                    item_design_id INTEGER NOT NULL,
                    ingredient_item_design_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL
                )
                """
            )
            conn.exec_driver_sql(
                """
                CREATE TABLE IF NOT EXISTS item_tags (
                    id INTEGER NOT NULL PRIMARY KEY,
                    item_design_id INTEGER NOT NULL,
                    tag VARCHAR(100) NOT NULL
                )
                """
            )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS crew_designs (
                id INTEGER NOT NULL PRIMARY KEY,
                crew_design_id INTEGER,
                name VARCHAR(255),
                name_es VARCHAR(255),
                description TEXT,
                race VARCHAR(100),
                role VARCHAR(100),
                stats JSON,
                raw_data JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS room_designs (
                id INTEGER NOT NULL PRIMARY KEY,
                room_design_id INTEGER,
                name VARCHAR(255),
                name_es VARCHAR(255),
                description TEXT,
                room_type VARCHAR(100),
                stats JSON,
                raw_data JSON,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            """
        )
        if "ship_designs" in tables:
            ship_info = conn.exec_driver_sql("PRAGMA table_info(ship_designs)").fetchall()
            ship_columns = {row[1] for row in ship_info}
            if "name_es" not in ship_columns:
                conn.exec_driver_sql("ALTER TABLE ship_designs ADD COLUMN name_es VARCHAR(255)")
        if "crew_designs" in tables:
            crew_info = conn.exec_driver_sql("PRAGMA table_info(crew_designs)").fetchall()
            crew_columns = {row[1] for row in crew_info}
            if "name_es" not in crew_columns:
                conn.exec_driver_sql("ALTER TABLE crew_designs ADD COLUMN name_es VARCHAR(255)")
        if "room_designs" in tables:
            room_info = conn.exec_driver_sql("PRAGMA table_info(room_designs)").fetchall()
            room_columns = {row[1] for row in room_info}
            if "name_es" not in room_columns:
                conn.exec_driver_sql("ALTER TABLE room_designs ADD COLUMN name_es VARCHAR(255)")
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS api_flow_events (
                id INTEGER NOT NULL PRIMARY KEY,
                session_id VARCHAR(64) NOT NULL,
                captured_at DATETIME,
                direction VARCHAR(16) NOT NULL,
                method VARCHAR(16),
                scheme VARCHAR(16),
                host VARCHAR(255),
                port INTEGER,
                path VARCHAR(2048),
                query TEXT,
                url_full TEXT,
                status_code INTEGER,
                duration_ms INTEGER,
                request_headers_json JSON,
                response_headers_json JSON,
                request_body_preview TEXT,
                response_body_preview TEXT,
                response_body_cleaned TEXT,
                request_size_bytes INTEGER,
                response_size_bytes INTEGER,
                content_type_request VARCHAR(255),
                content_type_response VARCHAR(255),
                tls BOOLEAN,
                error_text VARCHAR(2048),
                game_process_hint VARCHAR(255),
                flow_hash VARCHAR(100)
            )
            """
        )
        if "api_flow_events" in tables:
            api_flow_table_info = conn.exec_driver_sql("PRAGMA table_info(api_flow_events)").fetchall()
            existing_api_flow_columns = {row[1] for row in api_flow_table_info}
            for column_name, column_type in API_FLOW_EVENTS_SQLITE_COLUMNS.items():
                if column_name in existing_api_flow_columns:
                    continue
                conn.exec_driver_sql(f"ALTER TABLE api_flow_events ADD COLUMN {column_name} {column_type}")
            if "attacker_name" in existing_api_flow_columns:
                _drop_api_flow_events_attacker_name(conn)
                tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}

        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS battle_replays_normalized (
                id INTEGER NOT NULL PRIMARY KEY,
                api_flow_event_id INTEGER NOT NULL UNIQUE,
                battle_id INTEGER NOT NULL,
                captured_at DATETIME,
                attacking_ship_id INTEGER,
                defending_ship_id INTEGER,
                outcome_type VARCHAR(64),
                client_outcome_type VARCHAR(64),
                win_trophy_result INTEGER,
                win_minerals_result INTEGER,
                win_gas_result INTEGER,
                lose_trophy_result INTEGER,
                lose_minerals_result INTEGER,
                lose_gas_result INTEGER,
                battle_end_frame INTEGER,
                client_end_frame INTEGER,
                attacker_user_id INTEGER,
                attacker_name VARCHAR(255),
                attacker_trophy INTEGER,
                defender_user_id INTEGER,
                defender_name VARCHAR(255),
                defender_trophy INTEGER,
                battle_attributes_json JSON,
                attacker_user_attributes_json JSON,
                defender_user_attributes_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS battle_replay_ships (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_replay_id INTEGER NOT NULL,
                side VARCHAR(16) NOT NULL,
                ship_id INTEGER,
                ship_design_id INTEGER,
                ship_name VARCHAR(255),
                ship_level INTEGER,
                power_score INTEGER,
                hp FLOAT,
                ship_status VARCHAR(64),
                ship_attributes_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS battle_replay_rooms (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_replay_id INTEGER NOT NULL,
                side VARCHAR(16) NOT NULL,
                room_id INTEGER,
                room_design_id INTEGER,
                ship_id INTEGER,
                row INTEGER,
                column INTEGER,
                room_status VARCHAR(64),
                room_attributes_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS battle_replay_characters (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_replay_id INTEGER NOT NULL,
                side VARCHAR(16) NOT NULL,
                character_id INTEGER,
                ship_id INTEGER,
                character_design_id INTEGER,
                character_name VARCHAR(255),
                level INTEGER,
                xp INTEGER,
                character_attributes_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS battle_replay_commands (
                id INTEGER NOT NULL PRIMARY KEY,
                battle_replay_id INTEGER NOT NULL,
                command_order INTEGER NOT NULL,
                command_tag VARCHAR(64),
                user_id INTEGER,
                ship_id INTEGER,
                room_id INTEGER,
                character_id INTEGER,
                command_attributes_json JSON
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS player_matchup_logs (
                id INTEGER NOT NULL PRIMARY KEY,
                player_low_user_id INTEGER NOT NULL,
                player_high_user_id INTEGER NOT NULL,
                battle_id INTEGER NOT NULL,
                winner_user_id INTEGER,
                outcome_type VARCHAR(64),
                captured_at DATETIME,
                source_battle_replay_id INTEGER,
                source_api_flow_event_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            """
        )
        conn.exec_driver_sql(
            """
            CREATE TABLE IF NOT EXISTS player_matchup_stats (
                id INTEGER NOT NULL PRIMARY KEY,
                player_low_user_id INTEGER NOT NULL,
                player_high_user_id INTEGER NOT NULL,
                player_low_name VARCHAR(255),
                player_high_name VARCHAR(255),
                total_battles INTEGER NOT NULL DEFAULT 0,
                player_low_wins INTEGER NOT NULL DEFAULT 0,
                player_high_wins INTEGER NOT NULL DEFAULT 0,
                unknown_results INTEGER NOT NULL DEFAULT 0,
                last_battle_id INTEGER,
                last_winner_user_id INTEGER,
                last_captured_at DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
            """
        )


def ensure_sqlite_indexes() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" in tables:
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_item_type ON item_designs (item_type)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_rarity ON item_designs (rarity)")
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_level ON item_designs (level)")
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_designs_min_ship_level ON item_designs (min_ship_level)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_designs_min_room_level ON item_designs (min_room_level)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_designs_item_sub_type ON item_designs (item_sub_type)"
            )

        if "item_ingredients" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_item_ingredients_item_ing "
                "ON item_ingredients (item_design_id, ingredient_item_design_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_ingredients_item_design_id "
                "ON item_ingredients (item_design_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_ingredients_ingredient_item_design_id "
                "ON item_ingredients (ingredient_item_design_id)"
            )

        if "item_tags" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_item_tags_item_tag "
                "ON item_tags (item_design_id, tag)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_item_tags_item_design_id "
                "ON item_tags (item_design_id)"
            )
            conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_tags_tag ON item_tags (tag)")

        if "crew_designs" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_crew_designs_crew_design_id "
                "ON crew_designs (crew_design_id)"
            )

        if "room_designs" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_room_designs_room_design_id "
                "ON room_designs (room_design_id)"
            )

        if "api_flow_events" not in tables:
            return
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_api_flow_events_captured_at "
            "ON api_flow_events (captured_at DESC)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_api_flow_events_host_path "
            "ON api_flow_events (host, path)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_api_flow_events_status_captured "
            "ON api_flow_events (status_code, captured_at DESC)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_api_flow_events_session_id "
            "ON api_flow_events (session_id)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_api_flow_events_flow_hash "
            "ON api_flow_events (flow_hash)"
        )
        if "battle_replays_normalized" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_battle_replays_normalized_api_flow_event_id "
                "ON battle_replays_normalized (api_flow_event_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replays_normalized_battle_id "
                "ON battle_replays_normalized (battle_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replays_normalized_captured_at "
                "ON battle_replays_normalized (captured_at DESC)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replays_normalized_attacker_name "
                "ON battle_replays_normalized (attacker_name)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replays_normalized_defender_name "
                "ON battle_replays_normalized (defender_name)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replays_normalized_outcome_type "
                "ON battle_replays_normalized (outcome_type)"
            )
        if "battle_replay_ships" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_ships_battle_replay_id "
                "ON battle_replay_ships (battle_replay_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_ships_side "
                "ON battle_replay_ships (side)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_ships_ship_id "
                "ON battle_replay_ships (ship_id)"
            )
        if "battle_replay_rooms" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_rooms_battle_replay_id "
                "ON battle_replay_rooms (battle_replay_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_rooms_room_id "
                "ON battle_replay_rooms (room_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_rooms_ship_id "
                "ON battle_replay_rooms (ship_id)"
            )
        if "battle_replay_characters" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_characters_battle_replay_id "
                "ON battle_replay_characters (battle_replay_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_characters_character_id "
                "ON battle_replay_characters (character_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_characters_ship_id "
                "ON battle_replay_characters (ship_id)"
            )
        if "battle_replay_commands" in tables:
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_commands_battle_replay_id "
                "ON battle_replay_commands (battle_replay_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_battle_replay_commands_user_id "
                "ON battle_replay_commands (user_id)"
            )
        if "player_matchup_logs" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_player_matchup_logs_pair_battle "
                "ON player_matchup_logs (player_low_user_id, player_high_user_id, battle_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_player_matchup_logs_pair "
                "ON player_matchup_logs (player_low_user_id, player_high_user_id)"
            )
            conn.exec_driver_sql(
                "CREATE INDEX IF NOT EXISTS ix_player_matchup_logs_winner "
                "ON player_matchup_logs (winner_user_id)"
            )
        if "player_matchup_stats" in tables:
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS ux_player_matchup_stats_pair "
                "ON player_matchup_stats (player_low_user_id, player_high_user_id)"
            )


def _drop_api_flow_events_attacker_name(conn) -> None:
    table_info = conn.exec_driver_sql("PRAGMA table_info(api_flow_events)").fetchall()
    existing_columns = [row[1] for row in table_info]
    if "attacker_name" not in existing_columns:
        return

    try:
        try:
            conn.exec_driver_sql("ALTER TABLE api_flow_events DROP COLUMN attacker_name")
            return
        except Exception:
            pass

        keep_defs: list[str] = []
        keep_names: list[str] = []
        for _, name, col_type, notnull, dflt_value, pk in table_info:
            if name == "attacker_name":
                continue
            keep_names.append(name)
            definition = f"{name} {col_type}"
            if notnull:
                definition += " NOT NULL"
            if dflt_value is not None:
                definition += f" DEFAULT {dflt_value}"
            if pk:
                definition += " PRIMARY KEY"
            keep_defs.append(definition)

        conn.exec_driver_sql(f"CREATE TABLE api_flow_events_new ({', '.join(keep_defs)})")
        keep_names_csv = ", ".join(keep_names)
        conn.exec_driver_sql(
            f"INSERT INTO api_flow_events_new ({keep_names_csv}) "
            f"SELECT {keep_names_csv} FROM api_flow_events"
        )
        conn.exec_driver_sql("DROP TABLE api_flow_events")
        conn.exec_driver_sql("ALTER TABLE api_flow_events_new RENAME TO api_flow_events")
    except Exception:
        logger.warning("event=schema_drop_attacker_name_skipped reason=database_locked_or_sqlite_limits")


def _safe_int(value: Any) -> Optional[int]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return float(int(value))
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def _json_or_none(value: Any) -> Optional[str]:
    if value is None:
        return None
    return json.dumps(value)


def _parse_tags_value(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        return [tag.strip() for tag in value.split(",") if tag.strip()]
    if isinstance(value, (list, tuple, set)):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    return [str(value).strip()]


def _parse_ingredients_value(value: Any) -> list[tuple[int, int]]:
    if value is None:
        return []

    raw = value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return []
        try:
            raw = json.loads(value)
        except Exception:
            raw = value

    if isinstance(raw, str):
        parts = [part.strip() for part in raw.split("|") if part.strip()]
    elif isinstance(raw, (list, tuple, set)):
        parts = [str(part).strip() for part in raw if str(part).strip()]
    else:
        parts = [str(raw).strip()]

    output: list[tuple[int, int]] = []
    for part in parts:
        if "x" not in part:
            continue
        item_id_raw, qty_raw = part.split("x", 1)
        try:
            item_id = int(item_id_raw.strip())
            qty = int(qty_raw.strip())
        except ValueError:
            continue
        output.append((item_id, qty))
    return output


def repair_item_designs_json_columns() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" not in tables:
            return

        invalid_rows = conn.exec_driver_sql(
            """
            SELECT id, ingredients, metadata_json
            FROM item_designs
            WHERE (ingredients IS NOT NULL AND json_valid(ingredients) = 0)
               OR (metadata_json IS NOT NULL AND json_valid(metadata_json) = 0)
            """
        ).fetchall()
        if not invalid_rows:
            return

        for row_id, ingredients, metadata_json in invalid_rows:
            update_values = {"row_id": row_id}
            if ingredients is not None:
                try:
                    json.loads(ingredients)
                    update_values["ingredients"] = ingredients
                except Exception:
                    update_values["ingredients"] = json.dumps(ingredients)
            else:
                update_values["ingredients"] = None

            if metadata_json is not None:
                try:
                    json.loads(metadata_json)
                    update_values["metadata_json"] = metadata_json
                except Exception:
                    update_values["metadata_json"] = json.dumps(metadata_json)
            else:
                update_values["metadata_json"] = None

            conn.execute(
                text(
                    """
                    UPDATE item_designs
                    SET ingredients = :ingredients,
                        metadata_json = :metadata_json
                    WHERE id = :row_id
                    """
                ),
                update_values,
            )


def backfill_item_relations() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" not in tables or "item_ingredients" not in tables or "item_tags" not in tables:
            return

        rows = conn.exec_driver_sql(
            "SELECT item_design_id, tags, ingredients FROM item_designs WHERE item_design_id IS NOT NULL"
        ).fetchall()
        if not rows:
            return

        conn.exec_driver_sql("DELETE FROM item_ingredients")
        conn.exec_driver_sql("DELETE FROM item_tags")

        ingredient_rows: list[dict[str, Any]] = []
        tag_rows: list[dict[str, Any]] = []
        for item_design_id, tags, ingredients in rows:
            for tag in _parse_tags_value(tags):
                tag_rows.append({"item_design_id": item_design_id, "tag": tag})
            for ingredient_id, qty in _parse_ingredients_value(ingredients):
                ingredient_rows.append(
                    {
                        "item_design_id": item_design_id,
                        "ingredient_item_design_id": ingredient_id,
                        "quantity": qty,
                    }
                )

        if tag_rows:
            conn.execute(
                text("INSERT OR IGNORE INTO item_tags (item_design_id, tag) VALUES (:item_design_id, :tag)"),
                tag_rows,
            )
        if ingredient_rows:
            conn.execute(
                text(
                    """
                    INSERT OR IGNORE INTO item_ingredients
                    (item_design_id, ingredient_item_design_id, quantity)
                    VALUES (:item_design_id, :ingredient_item_design_id, :quantity)
                    """
                ),
                ingredient_rows,
            )


def migrate_item_designs_drop_raw_data() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" not in tables:
            return

        table_info = conn.exec_driver_sql("PRAGMA table_info(item_designs)").fetchall()
        existing_columns = [row[1] for row in table_info]
        if "raw_data" not in existing_columns:
            return

        columns_to_keep = [row for row in table_info if row[1] != "raw_data"]
        column_defs = []
        column_names = []
        for cid, name, col_type, notnull, dflt_value, pk in columns_to_keep:
            column_names.append(name)
            definition = f"{name} {col_type}"
            if notnull:
                definition += " NOT NULL"
            if dflt_value is not None:
                definition += f" DEFAULT {dflt_value}"
            if pk:
                definition += " PRIMARY KEY"
            column_defs.append(definition)

        conn.exec_driver_sql(f"CREATE TABLE item_designs_new ({', '.join(column_defs)})")
        conn.exec_driver_sql(
            f"INSERT INTO item_designs_new ({', '.join(column_names)}) "
            f"SELECT {', '.join(column_names)} FROM item_designs"
        )
        conn.exec_driver_sql("DROP TABLE item_designs")
        conn.exec_driver_sql("ALTER TABLE item_designs_new RENAME TO item_designs")

        # Recreate indexes used by the app.
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_id ON item_designs (id)")
        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_item_designs_item_design_id "
            "ON item_designs (item_design_id)"
        )


def log_schema_health() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        missing_tables = [name for name in ("item_designs", "item_ingredients", "item_tags") if name not in tables]
        if missing_tables:
            logger.warning("event=schema_missing_tables tables=%s", ",".join(missing_tables))
            return

        table_info = conn.exec_driver_sql("PRAGMA table_info(item_designs)").fetchall()
        existing_columns = {row[1] for row in table_info}
        missing_columns = [name for name in ITEM_DESIGNS_SQLITE_COLUMNS.keys() if name not in existing_columns]
        if missing_columns:
            logger.warning(
                "event=schema_missing_columns table=item_designs columns=%s",
                ",".join(missing_columns),
            )


def backfill_item_designs_columns() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" not in tables:
            return

        table_info = conn.exec_driver_sql("PRAGMA table_info(item_designs)").fetchall()
        existing_columns = {row[1] for row in table_info}
        if "raw_data" not in existing_columns:
            return

        tracked_columns = list(ITEM_DESIGNS_RAW_MAP.keys())
        needs_backfill_predicate = " OR ".join([f"{column} IS NULL" for column in tracked_columns])
        select_sql = (
            "SELECT id, raw_data FROM item_designs "
            "WHERE raw_data IS NOT NULL AND (" + needs_backfill_predicate + ")"
        )

        rows = conn.exec_driver_sql(select_sql).fetchall()
        if not rows:
            return

        for row_id, raw_data in rows:
            parsed = raw_data
            if isinstance(raw_data, str):
                try:
                    parsed = json.loads(raw_data)
                except Exception:
                    continue
            if not isinstance(parsed, dict):
                continue

            update_values: dict[str, Any] = {}
            for column_name, raw_key in ITEM_DESIGNS_RAW_MAP.items():
                value = parsed.get(raw_key)
                if column_name in {
                    "active_animation_id",
                    "animation_id",
                    "border_sprite_id",
                    "build_price",
                    "character_design_id",
                    "character_part_id",
                    "circulation",
                    "craft_design_id",
                    "equip_sound_file_id",
                    "flags",
                    "image_sprite_id",
                    "logo_sprite_id",
                    "missile_design_id",
                    "parent_item_design_id",
                    "particle_sprite_id",
                    "priority",
                    "race_id",
                    "rank",
                    "room_design_id",
                    "root_item_design_id",
                    "situation_design_id",
                    "sound_file_id",
                    "training_design_id",
                    "transaction_volume",
                    "level",
                    "min_ship_level",
                    "min_room_level",
                    "market_price",
                    "fair_price",
                    "build_time",
                    "mineral_cost",
                    "gas_cost",
                    "manufacture_cost",
                    "starbase_manufacture_cost",
                    "our_price",
                    "max_count",
                    "item_space",
                    "required_research_design_id",
                }:
                    update_values[column_name] = _safe_int(value)
                elif column_name in {"enhancement_value", "drop_chance", "reload_modifier", "reload_time"}:
                    update_values[column_name] = _safe_float(value)
                elif column_name in {"ingredients", "metadata_json"}:
                    update_values[column_name] = _json_or_none(value)
                else:
                    update_values[column_name] = str(value) if value is not None else None

            update_values["row_id"] = row_id
            set_sql = ", ".join([f"{column} = :{column}" for column in tracked_columns])
            conn.execute(
                text(f"UPDATE item_designs SET {set_sql} WHERE id = :row_id"),
                update_values,
            )


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
