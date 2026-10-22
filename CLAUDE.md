# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**PSS Logger Native** — a CLI tool that captures Pixel Starships battle traffic via mitmproxy, normalizes battle replays into SQLite, and generates Excel/CSV/JSON reports plus head-to-head (H2H) player stats.

**Stack**: Python 3.11+, mitmproxy, SQLAlchemy, Rich, PyInstaller.
**Entry point**: `pss-native` → `native_app/app/main.py`.

All development happens inside `native_app/`. The repo root holds only docs and CI config.

## Common commands

Run everything from `native_app/`.

### Setup
```bash
cd native_app
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

### Tests
```bash
# Full suite (~4s). Run from native_app/ because pyproject sets pythonpath=["."].
.venv/bin/python -m pytest

# Single test file
.venv/bin/python -m pytest tests/test_api_flow_capture.py

# Single test
.venv/bin/python -m pytest tests/test_api_flow_capture.py::test_name

# With coverage
.venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

### Run the app
```bash
# Installed console script
.venv/bin/pss-native

# Direct module (alternative from README)
python -m app.main

# Daemon mode (background capture only)
.venv/bin/pss-native --daemon start|stop|status
```

### Build
```bash
# PyInstaller one-file → portable ZIP under native_app/dist/
./scripts/build.sh
```
The build embeds `mitm_api_flow_addon.py` and a build-metadata JSON. It fails if `EXPECTED_MITM_ADDON_SHA256` in `app/services/api_flow_capture.py` mismatches the actual SHA of `mitm_api_flow_addon.py` — update the constant when you change the addon.

### Config
The `.env` file lives **inside** `native_app/`:
```bash
cp ../.env.dev.example .env
```
List-valued settings (`API_FLOW_IGNORE_HOSTS`, `API_FLOW_CAPTURE_HOST_ALLOWLIST`, etc.) require **JSON array** syntax, e.g. `API_FLOW_IGNORE_HOSTS=["host1","host2"]`. CSV was removed in v0.4.0.

## High-level architecture

### Entry & lifecycle (`app/main.py`)
`main()` resolves the DB path via `configure_environment()` (defaults to `~/.pss_logger/pss_logger.db`, overridable with `DATABASE_URL`), initializes SQLite schema + indexes, then starts capture failure-tolerantly via `ApiFlowRuntime.start_capture()` before launching `CliManager`. Capture failures are logged and the CLI continues without capture. Daemon mode (`--daemon start|stop|status`) runs capture only, no interactive menu.

### Data pipeline
```
mitmproxy addon (mitm_api_flow_addon.py)
  → stdout JSON lines prefixed "API_FLOW_EVENT "
  → ApiFlowCaptureManager (spawns mitmdump, parses lines)
  → ApiFlowRuntime (in-memory queue, flush thread, retention purge)
  → ApiFlowRepository.save_events() → api_flow_events table
  → same-call normalization → battle_replays_normalized + battle_replay_{ships,rooms,characters,commands}
  → player_matchup_logs / player_matchup_stats (H2H stats) + prune of obsolete replays
```
Capture is scoped by `API_FLOW_CAPTURE_HOST_ALLOWLIST` / `PATH_ALLOWLIST` (default: `api.pixelstarships.com` + `/BattleService/GetBattle3`) and `API_FLOW_IGNORE_HOSTS` (Unity telemetry hosts are passthrough). Sensitive headers are redacted before storage; response bodies are XML→JSON cleaned into `response_body_cleaned`.

### Layers
| Layer | Responsibility |
|-------|----------------|
| `app/main.py` | Entry, env config, DB init, capture bootstrap, CLI launch |
| `app/core/config.py` | Pydantic `Settings` (env + `.env`, JSON-array hinted decoding) |
| `app/core/build_info.py` | Version/git SHA from embedded build metadata |
| `app/models/database.py` | SQLAlchemy engine/session, `Base`, schema migrations (`ensure_sqlite_schema`), indexes |
| `app/models/pss_models.py` | SQLAlchemy ORM models (ApiFlowEvent, BattleReplay*, PlayerMatchup*, design tables) |
| `app/services/api_flow_capture.py` | `ApiFlowCaptureManager` — spawns mitmdump with the addon, SHA-256 integrity check, trusted-binary allowlist |
| `app/services/api_flow_runtime.py` | `ApiFlowRuntime` — queue, flush, startup sync (backfill cleaned bodies → sync replays → sync children → backfill rooms → matchup backfill + prune) |
| `app/services/api_flow_storage.py` | `ApiFlowRepository` — CRUD, purge by TTL/size, battle replay extraction from cleaned XML, design catalog sync, matchup stats recompute |
| `app/services/api_flow_list_service.py` | Paginated listing, H2H report data, battle detail with in-memory cache (`battle_detail_cache`) |
| `app/services/mitm_api_flow_addon.py` | mitmproxy addon that emits captured API flows as JSON to stdout |
| `app/cli/cli_manager.py` | Rich menu, 9 commands |
| `app/cli/concrete_commands.py` | Command implementations (query, reports, H2H, inspectors, capture, monitor, settings) |
| `app/cli/cli_services.py` | Service wrappers over list service + catalog resolvers for the CLI |
| `app/reporting/` | Excel/CSV/JSON report generators + templates |
| `app/daemon_manager.py` | Background capture daemon |

### CLI commands (9)
1. Consultar Eventos — query/filter API flow events
2. Generar Reportes — Excel/CSV/JSON battle report
3. Generar Reporte H2H — head-to-head player comparison
4. Inspector de Tripulante — character detail
5. Inspector de Salas — room detail (with `room_item_slot_mappings.json` slot resolution)
6. Inspector de Batalla — battle replay detail
7. Captura de Tráfico — start/stop/toggle/status of mitmproxy capture
8. Monitor de Sistema — CPU/RAM for a PID
9. Configuración — view/edit/export/import `.env` settings

### Key gotchas
- **DB path**: defaults to `~/.pss_logger/pss_logger.db` (created by `configure_environment()`).
- **Addon SHA**: `EXPECTED_MITM_ADDON_SHA256` in `api_flow_capture.py` must match `mitm_api_flow_addon.py` or the build/capture fails.
- **Line endings**: `.gitattributes` enforces LF for `.py` files.
- **Version**: single source in `pyproject.toml` (currently `0.4.0`); release number derives from the git tag `vX.Y.Z` — keep tag and pyproject aligned.
- **No GUI**: legacy Qt UI was removed; CLI-only via Rich. Don't resurrect Qt references.
- **Tests**: `pythonpath = ["."]` in pyproject — run pytest from `native_app/`. Tests use `tmp_path` fixtures and mock `ApiFlowRepository`. Windows mitmproxy tests are skipped on non-Windows.
- **Branch/version alignment**: `develop` = integration, `main` = stable; all changes via PR to `develop`; stable release = PR `develop → main` → tag `vX.Y.Z` on `main`.

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- When graphify-out/graph.json exists, run `graphify query "<question>"` before your first grep, search or source-file read for a codebase question, and put this rule in every subagent prompt that explores code. Read raw files only for lines the graph or an earlier read already located. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
- A committed graphify-out/graph.json is rewritten whole on every build, so a large diff to it in a pull request is expected. Do not flag it as churn or suggest skipping the graph rebuild or its hooks.
