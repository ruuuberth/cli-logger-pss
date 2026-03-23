# Logger PSS (Native Battle Replay)

Aplicación nativa para capturar, limpiar y normalizar replays de batallas de Pixel Starships.

## Vision actual

El proyecto está enfocado en un solo flujo:
1. Capturar tráfico del juego (excepto hosts en passthrough).
2. Limpiar payload para lectura técnica.
3. Normalizar datos en tablas relacionales para análisis y UI.

La UI principal muestra solo batallas `GetBattle3` ya normalizadas.

## Inicio rápido

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
```

## Base de datos

DB local de desarrollo:
- `native_app/pss_logger_dev.db`

Tablas clave:
- `api_flow_events` (evento capturado + `response_body_cleaned`)
- `battle_replays_normalized` (cabecera normalizada)
- `battle_replay_ships`
- `battle_replay_rooms`
- `battle_replay_characters`
- `battle_replay_commands`
- `player_matchup_logs` (historial minimo H2H por pareja y battle_id)
- `player_matchup_stats` (resumen H2H agregado por pareja)
- `ship_designs`
- `room_designs`
- `crew_designs`

La limpieza por retención/tamaño también elimina datos normalizados asociados.
El historial H2H (`player_matchup_logs`/`player_matchup_stats`) se conserva.

## Politica H2H (pareja de jugadores)

- La app conserva solo la batalla mas reciente por pareja de `user_id` (sin direccion).
- Si entra una batalla nueva para la misma pareja, elimina el replay anterior como obsoleto.
- Mantiene un mini logger historico en `player_matchup_logs` para calcular promedio.
- `delete_event` individual descuenta del logger/resumen.
- `clear history` limpia replay + logger + resumen.
- El `Battle Inspector` muestra el resumen y los ultimos resultados H2H.

## Variables relevantes

- `DATABASE_URL`
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

## Migración y backfill

```bash
cd native_app
python scripts/migrate_battle_replays_normalized.py
```

Este script:
- completa `response_body_cleaned` pendiente en `GetBattle3`
- sincroniza replay normalizado y tablas hijas
- sincroniza catálogos de diseño desde `DesignService/ListAllStaticDesigns2` (fallback)

## Catalogos locales (UI)

La UI prioriza catálogos locales del juego (`Data/Prod`) para traducir nombres
de naves, salas, tripulación y condiciones/acciones.

Fallbacks:
1. Archivos locales.
2. DB (`ship_designs`, `room_designs`, `crew_designs`) si existen.
3. Nombre existente o `Sin traduccion`.

Si no se detecta la ruta por defecto, el Inspector Manager permite definirla manualmente.

Tambien existe un mapeo manual versionado por sala para acciones `SetItem`
del inspector de IA. Ese mapping vive en
`native_app/app/resources/room_item_slot_mappings.json` y resuelve:

- `RoomDesignId + slot -> nombre canonico del item`
- nombre canonico -> nombre visible via `ItemDesigns.txt`, ignorando nivel

En tripulación, el inspector ya no expone `character_attributes_json` crudo
en la tabla principal. Ahora normaliza y consume:

- `CharacterActionsNormalized`
- `CharacterItemsNormalized`

La IA de tripulantes se traduce con `ActionTypes.txt` y `ConditionTypes.txt`.
El equipamiento se traduce con `ItemDesigns.txt`.

## Ramas

- Desarrollo nativo: `develop`
- Release estable: `main`
- PRs de features nativas: hacia `develop`

## Documentación

- `native_app/README.md`
- `docs/INSTALLATION.md`
- `docs/CODEBASE_ONBOARDING.md`
- `docs/WORKFLOW.md`
- `CONTRIBUTING.md`
