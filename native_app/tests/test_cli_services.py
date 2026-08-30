from __future__ import annotations

import pytest

from app.cli.cli_services import CharacterCliService, RoomCliService


class _FakeListService:
    def __init__(self, detail: dict | None) -> None:
        self.detail = detail

    def get_battle_detail(self, battle_replay_id: int) -> dict | None:
        return self.detail


_CHAR_ROW = {
    "id": 100,
    "battle_replay_id": 1,
    "side": "attacker",
    "character_id": 9001,
    "ship_id": 55,
    "character_design_id": 700,
    "character_design_name": "Capitana",
    "character_name": "Lara",
    "level": 12,
    "xp": 345,
    "character_attributes_json": {
        "CharacterActionsNormalized": [
            {"index": "0", "condition_type_id": "405", "action_type_id": "34", "character_action_id": "1"}
        ],
        "CharacterItemsNormalized": [
            {
                "index": "0",
                "item_id": "254905515",
                "item_design_id": "1982",
                "quantity": "1",
                "bonus_enhancement_type": "Ability",
                "bonus_enhancement_value": "13.4",
            }
        ],
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
    },
}

_ROOM_ROW = {
    "id": 200,
    "battle_replay_id": 1,
    "side": "attacker",
    "room_id": 1234,
    "room_design_id": 825,
    "room_design_name": "Hangar",
    "ship_id": 55,
    "row": 3,
    "column": 2,
    "room_status": "active",
    "room_attributes_json": {
        "RoomActionsNormalized": [
            {"index": "0", "condition_type_id": "405", "action_type_id": "70", "room_action_id": "1"}
        ]
    },
}

_DETAIL = {
    "characters": [_CHAR_ROW],
    "rooms": [_ROOM_ROW],
}


def test_character_list_returns_expected_keys() -> None:
    service = CharacterCliService(list_service=_FakeListService(_DETAIL))
    rows = service.list_characters(1)
    assert len(rows) == 1
    c = rows[0]
    assert c["id"] == 100
    assert c["character_id"] == 9001
    assert c["side"] == "attacker"
    assert c["name"] == "Lara"
    assert c["design_name"] == "Capitana"
    assert c["level"] == 12
    assert c["ship_id"] == 55


def test_character_list_empty_when_no_detail() -> None:
    service = CharacterCliService(list_service=_FakeListService(None))
    assert service.list_characters(1) == []


def test_character_inspect_resolves_stats_actions_items(tmp_path) -> None:
    from app.services.catalogo import CatalogoResolver
    catalogo = CatalogoResolver(tmp_path)
    service = CharacterCliService(list_service=_FakeListService(_DETAIL), catalogo=catalogo)
    detail = service.inspect_character(9001, 1, "attacker")
    assert "error" not in detail
    assert detail["name"] == "Lara"
    assert detail["design_name"] == "Capitana"
    assert detail["level"] == 12
    assert detail["xp"] == 345
    assert detail["actions"][0]["action_id"] == "34"
    assert detail["actions"][0]["character_action_id"] == "1"
    assert detail["items"][0]["item_design_id"] == "1982"
    assert detail["stats"]["stamina"] == "0"
    assert detail["stats"]["weapon_improvement"] == "9"


def test_character_inspect_by_replay_row_id() -> None:
    service = CharacterCliService(list_service=_FakeListService(_DETAIL))
    detail = service.inspect_character(100, 1, "attacker")
    assert detail["name"] == "Lara"


def test_character_inspect_missing_returns_error() -> None:
    service = CharacterCliService(list_service=_FakeListService(_DETAIL))
    detail = service.inspect_character(999, 1, "attacker")
    assert "error" in detail


def test_room_list_returns_expected_keys() -> None:
    service = RoomCliService(list_service=_FakeListService(_DETAIL))
    rows = service.list_rooms(1)
    assert len(rows) == 1
    r = rows[0]
    assert r["id"] == 200
    assert r["room_id"] == 1234
    assert r["side"] == "attacker"
    assert r["design_name"] == "Hangar"
    assert r["ship_id"] == 55
    assert r["row"] == 3
    assert r["column"] == 2


def test_room_list_empty_when_no_detail() -> None:
    service = RoomCliService(list_service=_FakeListService(None))
    assert service.list_rooms(1) == []


def test_room_inspect_resolves_actions(tmp_path) -> None:
    from app.services.catalogo import CatalogoResolver
    catalogo = CatalogoResolver(tmp_path)
    service = RoomCliService(list_service=_FakeListService(_DETAIL), catalogo=catalogo)
    detail = service.inspect_room(1234, 1, "attacker")
    assert "error" not in detail
    assert detail["design_name"] == "Hangar"
    assert detail["room_id"] == 1234
    assert detail["row"] == 3
    assert detail["actions"]
    assert detail["actions"][0]["action_type_id"] == "70"
    assert detail["actions"][0]["condition_type_id"] == "405"


def test_room_inspect_missing_returns_error() -> None:
    service = RoomCliService(list_service=_FakeListService(_DETAIL))
    detail = service.inspect_room(999, 1, "attacker")
    assert "error" in detail