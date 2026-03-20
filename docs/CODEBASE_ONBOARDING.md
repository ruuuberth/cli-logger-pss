# Onboarding Técnico

## Arquitectura

- UI: `native_app/app/ui/main_window.py`
- Captura runtime: `native_app/app/services/api_flow_capture.py`
- Addon mitm: `native_app/app/services/mitm_api_flow_addon.py`
- Persistencia/normalización: `native_app/app/services/api_flow_storage.py`
- Configuración: `native_app/app/core/config.py`
- Modelos DB: `native_app/app/models/pss_models.py`

## Flujo principal

1. Se captura tráfico vía proxy.
2. Se aplica passthrough por `API_FLOW_IGNORE_HOSTS`.
3. Se guarda evento en `api_flow_events`.
4. Se limpia payload en `response_body_cleaned`.
5. Se normaliza replay en tablas relacionales.
6. Se sincronizan catálogos (`ship_designs`, `room_designs`, `crew_designs`) desde `DesignService/ListAllStaticDesigns2` (fallback).
7. La UI usa catálogos locales (`Data/Prod`) como fuente principal de traducciones.

## Tablas de replay

- `battle_replays_normalized`
- `battle_replay_ships`
- `battle_replay_rooms`
- `battle_replay_characters`
- `battle_replay_commands`

## UI de inspección

- `Battle Inspector` funciona como manager.
- Abre subinspectores dedicados por tabla (Naves, Salas, Tripulación, Comandos).
- Las acciones `SetItem` del inspector de IA se resuelven con un mapping manual
  por sala en `native_app/app/resources/room_item_slot_mappings.json`, usando
  nombres canonicos del catalogo de items e ignorando nivel.

## Convenciones importantes

- El parser debe priorizar no perder datos del replay.
- El filtro de captura se aplica en addon (no en UI).
- Retención por TTL/tamaño debe mantener coherencia entre tablas.

## Comandos

```bash
cd native_app
source .venv/bin/activate
pytest -q
python -m pytest -q
python scripts/migrate_battle_replays_normalized.py
```
