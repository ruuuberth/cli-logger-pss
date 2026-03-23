# PSS Logger Native

Paquete nativo de captura y normalización de replays de batalla.

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
```

Alternativa:

```bash
python -m app.main
```

## Alcance funcional

La app captura tráfico desde `Flujo de la API` (excepto hosts en passthrough).  
La UI y normalización están enfocadas en replay de batalla (`/BattleService/GetBattle3`).

Pipeline:
1. Captura con `mitmdump`.
2. Persistencia en `api_flow_events`.
3. Limpieza a `response_body_cleaned`.
4. Normalización a tablas replay.
5. Sync de catálogos de diseño (`ship_designs`, `room_designs`, `crew_designs`).

Arquitectura de ventana principal:
- `app/ui/main_window.py`: solo UI, timers y wiring.
- `app/services/api_flow_runtime.py`: captura, backlog, flush y startup sync.
- `app/services/api_flow_list_service.py`: búsqueda, paginación y formateo de filas.
- `app/services/process_resource_monitor.py`: lectura de CPU/RAM desde `/proc`.
- `app/ui/api_flow_runtime_bridge.py`: bridge Qt fino entre runtime y ventana.

## Catalogos locales (UI)

La UI usa los catálogos locales del juego (`Data/Prod`) como fuente principal
para traducir nombres (naves, salas, tripulación y condiciones/acciones).

Fallbacks:
1. Archivos locales.
2. DB de diseño si existe.
3. `Sin traduccion`.

Puedes configurar la ruta desde el Inspector Manager.

Para acciones `SetItem` del inspector de IA, el proyecto mantiene un mapping
manual por sala en `app/resources/room_item_slot_mappings.json`. Ese archivo
resuelve placeholders de slot a nombres canonicos de item, y luego el nombre
visible sale de `ItemDesigns.txt` ignorando nivel.

El inspector de tripulación usa una capa equivalente, pero sin mapping manual:
- normaliza `CharacterActionsNormalized`
- normaliza `CharacterItemsNormalized`
- traduce IA con `ActionTypes.txt` y `ConditionTypes.txt`
- traduce equipamiento con `ItemDesigns.txt`

La tabla principal de tripulantes ya no muestra `character_attributes_json`
crudo; expone stats limpias y botones de `Equipo` e `Inspector IA`.

## Variables de entorno

- `API_FLOW_ENABLED`
- `MITMPROXY_BINARY`
- `MITMPROXY_LISTEN_HOST`
- `MITMPROXY_LISTEN_PORT`
- `API_FLOW_BODY_MAX_CHARS`
- `API_FLOW_RETENTION_DAYS`
- `API_FLOW_MAX_DB_MB`
- `API_FLOW_IGNORE_HOSTS`
- `API_FLOW_CAPTURE_HOST_ALLOWLIST`
- `API_FLOW_CAPTURE_PATH_ALLOWLIST`

## DB local

Con `.env.dev.example`:
- URL: `sqlite:///./pss_logger_dev.db`
- archivo: `native_app/pss_logger_dev.db`

## Migración de historico

```bash
python scripts/migrate_battle_replays_normalized.py
```

Backfill:
- `response_body_cleaned`
- `battle_replays_normalized`
- `battle_replay_ships`
- `battle_replay_rooms`
- `battle_replay_characters`
- `battle_replay_commands`

## Build

```bash
./scripts/build.sh
```
