# Onboarding Técnico

## Arquitectura

- UI: `native_app/app/ui/main_window.py`
- Bridge Qt del runtime: `native_app/app/ui/api_flow_runtime_bridge.py`
- Captura runtime: `native_app/app/services/api_flow_capture.py`
- Coordinador runtime del flujo: `native_app/app/services/api_flow_runtime.py`
- Servicio de listado/paginación: `native_app/app/services/api_flow_list_service.py`
- Cache de detalle de batalla: `native_app/app/services/battle_detail_cache.py`
- Métricas ligeras de rendimiento: `native_app/app/services/perf_metrics.py`
- Monitor de recursos del sistema: `native_app/app/services/process_resource_monitor.py`
- Addon mitm: `native_app/app/services/mitm_api_flow_addon.py`
- Persistencia/normalización: `native_app/app/services/api_flow_storage.py`
- Configuración: `native_app/app/core/config.py`
- Modelos DB: `native_app/app/models/pss_models.py`
- Modelos/delegates Qt del flujo:
  - `native_app/app/ui/models/api_flow_table_model.py`
  - `native_app/app/ui/delegates/row_action_delegate.py`

## Flujo principal

1. Se captura tráfico vía proxy.
2. Se aplica passthrough por `API_FLOW_IGNORE_HOSTS`.
3. `ApiFlowRuntime` mantiene backlog, flush periódico y flush final.
4. Se guarda evento en `api_flow_events`.
5. Se limpia payload en `response_body_cleaned`.
6. Se normaliza replay en tablas relacionales.
7. Se sincronizan catálogos (`ship_designs`, `room_designs`, `crew_designs`) desde `DesignService/ListAllStaticDesigns2` (fallback).
8. La UI usa catálogos locales (`Data/Prod`) como fuente principal de traducciones.

## Responsabilidades

- `MainWindow` no debe contener parsing, persistencia ni lógica de captura.
- `ApiFlowRuntime` es la única capa que conoce simultáneamente `ApiFlowCaptureManager`
  y `ApiFlowRepository`.
- `ApiFlowListService` prepara las filas visibles de la tabla principal.
- `BattleDetailCache` evita recomputar serialización completa al reabrir batallas recientes.
- `ProcessResourceMonitor` encapsula la lectura de `/proc` y el cálculo de CPU/RAM.
- La tabla principal del flujo debe mantenerse en `QTableView + model + delegate`,
  no volver a `QTableWidget` con widgets por fila.

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
- El inspector de tripulación usa `CharacterActionsNormalized` y
  `CharacterItemsNormalized` dentro de `battle_replay_characters.character_attributes_json`
  para renderizar IA, equipo y stats limpias sin exponer el JSON crudo en la UI.

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
