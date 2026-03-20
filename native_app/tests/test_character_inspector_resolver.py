from __future__ import annotations

from app.services.catalogo import CatalogoResolver
from app.services.character_inspector_resolver import CharacterInspectorResolver


def test_has_actions_detects_normalized_payload(tmp_path) -> None:
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "CharacterActionsNormalized": [
                {"index": "0", "condition_type_id": "405", "action_type_id": "34", "character_action_id": "1"}
            ]
        }
    }
    assert resolver.has_actions(character) is True


def test_has_actions_rebuilds_from_raw_keys(tmp_path) -> None:
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "CharacterActions.CharacterAction[0].ActionTypeId": "34",
            "CharacterActions.CharacterAction[0].ConditionTypeId": "405",
            "CharacterActions.CharacterAction[0].CharacterActionId": "1",
        }
    }
    assert resolver.has_actions(character) is True


def test_get_character_actions_translates_types(tmp_path) -> None:
    (tmp_path / "ActionTypes.txt").write_text(
        '<ActionTypes><ActionType ActionTypeId="34" ActionTypeName="Usar habilidad"/></ActionTypes>',
        encoding="utf-8",
    )
    (tmp_path / "ConditionTypes.txt").write_text(
        '<ConditionTypes><ConditionType ConditionTypeId="405" ConditionTypeName="Aviones enemigos activos > 5"/></ConditionTypes>',
        encoding="utf-8",
    )
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "CharacterActionsNormalized": [
                {"index": "0", "condition_type_id": "405", "action_type_id": "34", "character_action_id": "1"}
            ]
        }
    }
    actions = resolver.get_character_actions(character)
    assert actions[0]["index"] == "1"
    assert actions[0]["action_label"] == "Usar habilidad"
    assert actions[0]["condition_label"] == "Aviones enemigos activos > 5"


def test_has_items_detects_raw_keys(tmp_path) -> None:
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {"character_attributes_json": {"Items.Item[0].ItemDesignId": "1982"}}
    assert resolver.has_items(character) is True


def test_get_character_items_translates_item_design(tmp_path) -> None:
    (tmp_path / "ItemDesigns.txt").write_text(
        '<ItemDesigns><ItemDesign ItemDesignId="1982" ItemDesignName="Chaleco Web"/></ItemDesigns>',
        encoding="utf-8",
    )
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "CharacterItemsNormalized": [
                {
                    "index": "0",
                    "item_id": "254905515",
                    "item_design_id": "1982",
                    "quantity": "1",
                    "bonus_enhancement_type": "Ability",
                    "bonus_enhancement_value": "13.4",
                }
            ]
        }
    }
    items = resolver.get_character_items(character)
    assert items[0]["index"] == "1"
    assert items[0]["item_name"] == "Chaleco Web"
    assert items[0]["bonus_type"] == "Ability"


def test_get_character_stats_summary_extracts_clean_fields(tmp_path) -> None:
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "RoomId": "192565921",
            "ShipId": "8761013",
            "Stamina": "0",
            "Fatigue": "1",
            "AttackImprovement": "2",
            "RepairImprovement": "3",
            "PilotImprovement": "4",
            "ScienceImprovement": "5",
            "EngineImprovement": "6",
            "AbilityImprovement": "7",
            "HpImprovement": "8",
            "WeaponImprovement": "9",
            "TrainingDesignId": "0",
            "TrainingEndDate": "2026-03-19T07:47:59",
        }
    }
    stats = resolver.get_character_stats_summary(character)
    assert stats["room_id"] == "192565921"
    assert stats["weapon_improvement"] == "9"
    assert stats["training"] == "2026-03-19T07:47:59"


def test_resolver_fallbacks_when_catalog_missing(tmp_path) -> None:
    resolver = CharacterInspectorResolver(CatalogoResolver(tmp_path))
    character = {
        "character_attributes_json": {
            "Items.Item[0].ItemDesignId": "1982",
            "CharacterActions.CharacterAction[0].ActionTypeId": "34",
            "CharacterActions.CharacterAction[0].ConditionTypeId": "405",
        }
    }
    items = resolver.get_character_items(character)
    actions = resolver.get_character_actions(character)
    assert items[0]["item_name"] == "ItemDesignId 1982"
    assert actions[0]["action_label"] == "34"
    assert actions[0]["condition_label"] == "405"
