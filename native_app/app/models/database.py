import json
import logging
from typing import Any, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

logger = logging.getLogger(__name__)


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


def ensure_sqlite_schema() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        tables = {row[0] for row in conn.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'")}
        if "item_designs" not in tables:
            return

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


def ensure_sqlite_indexes() -> None:
    if engine.dialect.name != "sqlite":
        return

    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_item_type ON item_designs (item_type)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_rarity ON item_designs (rarity)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_level ON item_designs (level)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_min_ship_level ON item_designs (min_ship_level)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_min_room_level ON item_designs (min_room_level)")
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_designs_item_sub_type ON item_designs (item_sub_type)")

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

        conn.exec_driver_sql(
            "CREATE UNIQUE INDEX IF NOT EXISTS ux_item_tags_item_tag "
            "ON item_tags (item_design_id, tag)"
        )
        conn.exec_driver_sql(
            "CREATE INDEX IF NOT EXISTS ix_item_tags_item_design_id "
            "ON item_tags (item_design_id)"
        )
        conn.exec_driver_sql("CREATE INDEX IF NOT EXISTS ix_item_tags_tag ON item_tags (tag)")


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
