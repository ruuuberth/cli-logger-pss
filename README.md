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
- `ship_designs`
- `room_designs`
- `crew_designs`

La limpieza por retención/tamaño también elimina datos normalizados asociados.

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
- sincroniza catálogos de diseño desde `DesignService/ListAllStaticDesigns2`

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
