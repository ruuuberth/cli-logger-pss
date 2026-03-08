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
