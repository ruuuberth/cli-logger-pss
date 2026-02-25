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

## Items sources

- `BaseDeDatos`: reads parsed rows from local SQLite.
- `API`: fetches official endpoint and updates local DB.
- `ArchivosLocales`: parses imported `ItemDesigns.txt`.
- API item cache TTL uses `ITEMS_API_CACHE_TTL_SECONDS` (default `86400` = 1 day).
- API request timeout uses `PSS_API_REQUEST_TIMEOUT_SECONDS`.

## VSCode

- Debug configuration: `.vscode/launch.json` -> `Native App (Debug)`.
- Run task: `.vscode/tasks.json` -> `Run Native App`.
