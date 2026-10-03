# Onboarding Técnico

## Arquitectura

- Entry point: `native_app/app/main.py`
- Menú CLI (Rich): `native_app/app/cli/cli_manager.py` (9 comandos)
- Comandos concretos: `native_app/app/cli/concrete_commands.py`
- Wrappers de servicios para la CLI: `native_app/app/cli/cli_services.py`
- Captura runtime: `native_app/app/services/api_flow_capture.py`
- Coordinador runtime del flujo: `native_app/app/services/api_flow_runtime.py`
- Daemon de captura en background: `native_app/app/daemon_manager.py`
- Servicio de listado/paginación: `native_app/app/services/api_flow_list_service.py`
- Cache de detalle de batalla: `native_app/app/services/battle_detail_cache.py`
- Métricas ligeras de rendimiento: `native_app/app/services/perf_metrics.py`
- Monitor de recursos del sistema: `native_app/app/services/process_resource_monitor.py`
- Addon mitm: `native_app/app/services/mitm_api_flow_addon.py`
- Persistencia/normalización: `native_app/app/services/api_flow_storage.py`
- Configuración: `native_app/app/core/config.py`
- Modelos DB: `native_app/app/models/pss_models.py`
- Resolución de catálogos del juego (Data/Prod): `native_app/app/services/catalogo.py`
- Inspectores de batalla/salas/tripulación: `battle_inspector_resolver.py`, `room_item_mapping.py`, `character_inspector_resolver.py`, `battle_inspector_exporter.py` (en `services/`)
- Reporting: `native_app/app/reporting/` (XLSX/CSV/JSON)

> **Nota histórica**: la UI Qt fue eliminada. No existe `app/ui/` — toda interacción es por consola (Rich). Los servicios que alimentaban la UI (`battle_detail_cache`, `perf_metrics`, `process_resource_monitor`, `room_item_mapping`, `character_inspector_resolver`) siguen vivos y los consumen los inspectores CLI vía `cli_services`.

## Flujo principal

1. Se captura tráfico vía proxy (mitmproxy, addon `mitm_api_flow_addon.py`).
2. Se aplica passthrough por `API_FLOW_IGNORE_HOSTS` y filtros por allowlist.
3. `ApiFlowRuntime` mantiene backlog, flush periódico y flush final.
4. Se guarda evento en `api_flow_events` (body crudo en `response_body_preview`).
5. Se limpia payload a `response_body_cleaned` (XML→JSON; atributos internos llegan HTML-escaped).
6. Se normaliza replay en tablas relacionales (same-call normalization).
7. Se sincronizan catálogos (`ship_designs`, `room_designs`, `crew_designs`) desde `DesignService/ListAllStaticDesigns2` (fallback).
8. Los inspectores CLI usan catálogos locales del juego (`~/.config/unity3d/SavySoda/Pixel Starships/Data/Prod`, auto-detectado por `CatalogoResolver.default_base_dir()`) como fuente principal de traducciones.
9. Se aplica ciclo H2H por pareja: logger mínimo + stats + poda de replays obsoletos.

## Responsabilidades

- El código de CLI (`app/cli/*`) no debe contener parsing ni persistencia — delega en `cli_services` y el resto de servicios.
- `ApiFlowRuntime` es la única capa que conoce simultáneamente `ApiFlowCaptureManager` y `ApiFlowRepository`.
- `ApiFlowListService` prepara las filas visibles del listado principal (paginación + cache de detalle).
- `BattleDetailCache` evita recomputar serialización completa al reabrir batallas recientes.
- `ProcessResourceMonitor` encapsula la lectura de `/proc` y el cálculo de CPU/RAM.
- La resolución de nombres (naves/salas/tripulación/items) pasa siempre por `CatalogoResolver`; el fallback es `Sin traducción`.

## Tablas de replay

- `battle_replays_normalized`
- `battle_replay_ships`
- `battle_replay_rooms`
- `battle_replay_characters`
- `battle_replay_commands`
- `player_matchup_logs`
- `player_matchup_stats`

## Ciclo H2H por pareja

- Clave de pareja: `user_id` sin dirección (A vs B = B vs A).
- Inserción nueva:
  1. Inserta log mínimo (`pair + battle_id + winner`, sin duplicados por pareja+battle_id).
  2. Poda replays obsoletos de esa pareja: conserva los N más recientes **por batalla distinta** (`API_FLOW_REPLAYS_PER_PAIR`, default 1).
  3. Recalcula stats agregadas de la pareja.
- Backfill de arranque: puebla logger histórico faltante, recalcula stats, poda replays obsoletos existentes.
- `delete_event` individual: elimina replay/evento y descuenta del logger/stats de la pareja.
- Reporte H2H (comando 3 del menú): genera `_Resumen`, `_Batallas`, `_Tendencias` y (si hay datos) `_Flota` en Excel; JSON incluye `fleet_breakdown`.

## Inspectores CLI

- `Inspector de Tripulante` (4) y `Inspector de Salas` (5) usan `character_inspector_resolver` / `room_item_mapping` sobre las tablas normalizadas.
- Las acciones `SetItem` se resuelven con el mapping manual por sala en `native_app/app/resources/room_item_slot_mappings.json`, usando nombres canónicos del catálogo de items e ignorando nivel.
- El inspector de tripulación usa `CharacterActionsNormalized` y `CharacterItemsNormalized` dentro de `battle_replay_characters.character_attributes_json` para renderizar IA, equipo y stats limpias sin exponer el JSON crudo.
- `Inspector de Batalla` (6) imprime el detalle del replay por clave-valor tras sincronizar eventos pendientes (`runtime.flush_pending()`).

## Convenciones importantes

- El parser debe priorizar no perder datos del replay.
- El filtro de captura se aplica en addon (no en CLI).
- Retención por TTL/tamaño debe mantener coherencia entre tablas.

## Comandos

```bash
cd native_app
.venv/bin/python -m pytest -q          # suite completa (140 tests)
python -m app.main                     # arranca la CLI
pss-native                             # entry point instalado
pss-native --daemon start|stop|status  # daemon de captura
python scripts/migrate_battle_replays_normalized.py
```
