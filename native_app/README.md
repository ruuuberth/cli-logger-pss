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
6. Consolidación H2H por pareja (`player_matchup_logs`, `player_matchup_stats`) y poda de replay obsoleto.

Arquitectura de ventana principal:
- `app/ui/main_window.py`: solo UI, timers y wiring.
- `app/services/api_flow_runtime.py`: captura, backlog, flush y startup sync.
- `app/services/api_flow_list_service.py`: búsqueda, paginación, formateo de filas y cache de detalle.
- `app/services/process_resource_monitor.py`: lectura de CPU/RAM desde `/proc`.
- `app/ui/api_flow_runtime_bridge.py`: bridge Qt fino entre runtime y ventana.
- `app/ui/models/api_flow_table_model.py`: modelo de la tabla principal del flujo.
- `app/ui/delegates/row_action_delegate.py`: acciones por fila sin `QPushButton` reales.
- `app/services/perf_metrics.py`: medición ligera de hotspots en desarrollo.

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

## Rendimiento

La tabla principal del flujo ya no usa `QTableWidget` ni `setCellWidget()` por
fila. Usa `QTableView + model + delegate`, con lo que el scroll y el repintado
son bastante más baratos en CPU y RAM.

El `BattleInspectorWindow` sigue la misma dirección para sus tablas más pesadas
(`Salas`, `Tripulación`, `Comandos`, `IA`, `Equipo`), y evita `resizeRowsToContents()`
global para no pagar ese coste en cada apertura.

La apertura de detalles de batalla usa cache en memoria para replays recientes,
y el listado principal usa una query más ligera que evita materializar filas ORM
completas cuando no hace falta.

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

Defaults recomendados para rendimiento:
- `API_FLOW_CAPTURE_HOST_ALLOWLIST=api.pixelstarships.com`
- `API_FLOW_CAPTURE_PATH_ALLOWLIST=/BattleService/GetBattle3`
- `API_FLOW_IGNORE_HOSTS` debe incluir hosts Unity de auth/config/perf para evitar ruido TLS.

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
- `player_matchup_logs`
- `player_matchup_stats`

## Politica H2H

- Pareja canonica: `(min(attacker_user_id, defender_user_id), max(...))`.
- Solo queda 1 replay vigente por pareja (el mas reciente por `captured_at/id`).
- El mini logger H2H guarda ganador por `battle_id` sin duplicados por pareja.
- El resumen H2H se recalcula desde logger y se muestra en el `Battle Inspector`.
- Purga por TTL/tamano borra replay viejo, pero conserva logger/resumen.

## Build

```bash
./scripts/build.sh
```

## CI/CD de binarios

Workflows:
- `Native Build` (`.github/workflows/native-build.yml`):
  - corre en `push`/`PR` a `develop` y `main`
  - compila Linux + Windows
  - publica artifacts de run:
    - `pss-logger-native-linux`
    - `pss-logger-native-windows.exe`
- `Native Pre-release (develop)` (`.github/workflows/prerelease-develop.yml`):
  - corre en `push` a `develop`
  - publica canal `develop-latest` como pre-release
  - adjunta binarios + `SHA256SUMS.txt` (+ firma opcional)
- `Native Release` (`.github/workflows/release.yml`):
  - corre en tags `v*`
  - publica release estable con binarios Linux/Windows
  - adjunta `SHA256SUMS.txt` (+ firma opcional)

Firma opcional:
- si existe `SIGNING_PRIVATE_KEY` (y opcionalmente `SIGNING_PASSPHRASE`) se firma `SHA256SUMS.txt` como `SHA256SUMS.txt.asc`
- si no existen secretos, el release sigue sin fallo

Operación rápida:
1. Pre-release: push a `develop`.
2. Release estable: `git tag vX.Y.Z && git push origin vX.Y.Z`.
3. Verificar descarga: comparar hash local contra `SHA256SUMS.txt`.
