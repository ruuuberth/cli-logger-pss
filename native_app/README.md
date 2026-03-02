# PSS Logger Native

Native desktop app package for PixelStarships Logger.

## Development quickstart

### First run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
```

### Next runs

```bash
source .venv/bin/activate
pss-native
```

Alternative entrypoint:

```bash
python -m app.main
```

## About `venv`

- `python3 -m venv .venv`: creates an isolated Python environment in this folder.
- `source .venv/bin/activate`: activates it for the current terminal session.
- `deactivate`: exits the environment.
- In a new terminal, activate it again before running the app.

Quick check:
```bash
which python
which pip
```

Both should point to `native_app/.venv/...`.

## Dev database

- With `native_app/.env` from `.env.dev.example`, app uses `sqlite:///./pss_logger_dev.db`.
- Effective local file: `native_app/pss_logger_dev.db`.
- Fallback (if `DATABASE_URL` is not set): `~/.pss_logger/pss_logger.db`.

## App focus

- Current UI is focused on `Flujo de la API` for battle logging.
- Local file import and direct catalog/item API options are removed from the main navigation.

## VSCode

- Debug configuration: `.vscode/launch.json` -> `Native App (Debug)`.
- Run task: `.vscode/tasks.json` -> `Run Native App`.

## API Flow tab (mitmproxy)

- New tab: `Flujo de la API` for live request/response capture.
- Starts/stops `mitmdump` from the app and stores history in SQLite.
- Requires proxy setup in game/client (`127.0.0.1:8081` by default).

Environment variables:
- `API_FLOW_ENABLED`
- `MITMPROXY_BINARY`
- `MITMPROXY_LISTEN_HOST`
- `MITMPROXY_LISTEN_PORT`
- `API_FLOW_BODY_MAX_CHARS`
- `API_FLOW_RETENTION_DAYS`
- `API_FLOW_MAX_DB_MB`
- `API_FLOW_IGNORE_HOSTS` (comma-separated passthrough hosts)
