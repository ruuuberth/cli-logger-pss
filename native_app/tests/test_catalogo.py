from __future__ import annotations

from app.services.catalogo import CatalogoResolver


def test_format_name_strips_numeric_parens() -> None:
    resolver = CatalogoResolver(None)
    assert (
        resolver.format_name("No hay aviones enemigos activos (80)")
        == "No hay aviones enemigos activos"
    )
    assert resolver.format_name("Nombre (Beta)") == "Nombre (Beta)"


def test_resolve_design_name_local(tmp_path) -> None:
    xml = '<ShipDesigns><ShipDesign ShipDesignId="1" ShipDesignName="Fragata (10)"/></ShipDesigns>'
    (tmp_path / "ShipDesigns.txt").write_text(xml, encoding="utf-8")
    resolver = CatalogoResolver(tmp_path)
    assert resolver.resolve_design_name(1, "", "ship") == "Fragata"


def test_resolve_design_name_fallback_current_name(tmp_path) -> None:
    resolver = CatalogoResolver(tmp_path)
    assert resolver.resolve_design_name(99, "Nombre (7)", "ship") == "Nombre"


def test_resolve_item_name_local(tmp_path) -> None:
    xml = '<ItemDesigns><ItemDesign ItemDesignId="2231" ItemDesignName="Dron de misiles (99)"/></ItemDesigns>'
    (tmp_path / "ItemDesigns.txt").write_text(xml, encoding="utf-8")
    resolver = CatalogoResolver(tmp_path)
    assert resolver.resolve_item_name(2231) == "Dron de misiles"


def test_resolve_item_name_fallback_when_missing(tmp_path) -> None:
    resolver = CatalogoResolver(tmp_path)
    assert resolver.resolve_item_name(2231, fallback="Elegir objeto") == "Elegir objeto"


def test_resolve_item_name_from_base_ignores_level(tmp_path) -> None:
    xml = (
        "<ItemDesigns>"
        '<ItemDesign ItemDesignId="2236" ItemDesignName="Dron ECM de misiles Nivel 2" ItemDesignNameEN="Missile ECM Drone Lv2"/>'
        "</ItemDesigns>"
    )
    (tmp_path / "ItemDesigns.txt").write_text(xml, encoding="utf-8")
    resolver = CatalogoResolver(tmp_path)
    assert resolver.resolve_item_name_from_base("Missile ECM Drone") == "Dron ECM de misiles"
