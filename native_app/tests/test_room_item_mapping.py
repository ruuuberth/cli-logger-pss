from __future__ import annotations

import json

from app.services.catalogo import CatalogoResolver
from app.services.room_item_mapping import RoomItemMappingResolver


def test_get_slot_index_for_set_item_actions() -> None:
    resolver = RoomItemMappingResolver()
    assert resolver.get_slot_index_for_action_type(70) == 0
    assert resolver.get_slot_index_for_action_type("74") == 4
    assert resolver.get_slot_index_for_action_type("75") == 5
    assert resolver.get_slot_index_for_action_type("55") is None


def test_get_item_name_base_for_hangar_825(tmp_path) -> None:
    mapping = {
        "version": 1,
        "rooms": {
            "825": {
                "slots": {
                    "0": {"item_name_en_base": "Laser Turret Drone"},
                    "1": {"item_name_en_base": "Missile Turret Drone"},
                    "2": {"item_name_en_base": "Repair Drone"},
                    "3": {"item_name_en_base": "Shield Drone"},
                    "4": {"item_name_en_base": "Missile ECM Drone"},
                }
            }
        },
    }
    mapping_path = tmp_path / "room_item_slot_mappings.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    resolver = RoomItemMappingResolver(mapping_path=mapping_path)
    assert resolver.get_item_name_base(825, 0) == "Laser Turret Drone"
    assert resolver.get_item_name_base(825, 1) == "Missile Turret Drone"
    assert resolver.get_item_name_base(825, 2) == "Repair Drone"
    assert resolver.get_item_name_base(825, 3) == "Shield Drone"
    assert resolver.get_item_name_base(825, 4) == "Missile ECM Drone"


def test_resolve_action_label_uses_item_catalog(tmp_path) -> None:
    mapping = {
        "version": 1,
        "rooms": {
            "825": {
                "slots": {
                    "4": {"item_name_en_base": "Missile ECM Drone"},
                }
            }
        },
    }
    mapping_path = tmp_path / "room_item_slot_mappings.json"
    mapping_path.write_text(json.dumps(mapping), encoding="utf-8")
    item_xml = (
        '<ItemDesigns>'
        '<ItemDesign ItemDesignId="2236" ItemDesignName="Dron ECM de misiles Nivel 2" ItemDesignNameEN="Missile ECM Drone Lv2"/>'
        "</ItemDesigns>"
    )
    (tmp_path / "ItemDesigns.txt").write_text(item_xml, encoding="utf-8")
    catalogo = CatalogoResolver(tmp_path)
    resolver = RoomItemMappingResolver(mapping_path=mapping_path, catalogo=catalogo)
    assert resolver.resolve_action_label(825, 74, "Elegir objeto {4}") == "Elegir objeto Dron ECM de misiles"


def test_resolve_action_label_falls_back_when_room_missing(tmp_path) -> None:
    mapping_path = tmp_path / "room_item_slot_mappings.json"
    mapping_path.write_text(json.dumps({"version": 1, "rooms": {}}), encoding="utf-8")
    resolver = RoomItemMappingResolver(mapping_path=mapping_path, catalogo=CatalogoResolver(tmp_path))
    assert resolver.resolve_action_label(999, 74, "Elegir objeto {4}") == "Elegir objeto {4}"
