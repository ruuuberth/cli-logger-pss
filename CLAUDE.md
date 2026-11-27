# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

**PSS Logger Native** — a CLI tool that captures Pixel Starships battle traffic via mitmproxy, normalizes battle replays into SQLite, and generates Excel/CSV/JSON reports plus head-to-head (H2H) player stats.

**Stack**: Python 3.11+, mitmproxy, SQLAlchemy, Rich, Textual (TUI), PyInstaller.
**Entry point**: `pss-native` → `native_app/app/main.py`.

All development happens inside `native_app/`. The repo root holds only docs and CI config.

## Common commands

Run everything from `native_app/` (pyproject sets `pythonpath = ["."]`, so pytest/ruff paths are relative to it).

### Setup
```bash
cd native_app
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp ../.env.example .env   # optional; app works with defaults
```

### Tests
```bash
.venv/bin/python -m pytest                                    # full suite
.venv/bin/python -m pytest tests/test_api_flow_capture.py     # single file
.venv/bin/python -m pytest tests/test_api_flow_capture.py::test_name  # single test
.venv/bin/python -m pytest --cov=app --cov-report=term-missing
```

### Lint (both enforced by CI on Linux and Windows)
```bash
.venv/bin/python -m ruff check app/ tests/
.venv/bin/python -m ruff format --check app/ tests/
.venv/bin/python -m ruff format app/ tests/   # auto-fix formatting
```

### Run the app
```bash
.venv/bin/pss-native                      # interactive Rich CLI menu (9 commands)
.venv/bin/pss-native --tui                # Textual TUI: live dashboard, battle explorer, detail inspector
.venv/bin/pss-native --daemon start|stop|status   # background capture only, no menu
# TUI keys: n/p paginate · enter detail · / search + enter filter · r reload · s capture toggle · q quit
```

### Build
```bash
# PyInstaller one-file → portable ZIP under native_app/dist/ (no loose binaries in releases)
./scripts/build.sh          # Windows: ./scripts/build.ps1 (PowerShell)
```
The build embeds `mitm_api_flow_addon.py` and a build-metadata JSON. It fails if `EXPECTED_MITM_ADDON_SHA256` in `app/services/api_flow_capture.py` mismatches the actual SHA of `mitm_api_flow_addon.py` — update the constant when you change the addon.

### Windows notes
Use `.venv/Scripts/python.exe` and `.venv/Scripts/pss-native.exe`; `python3` and `source .venv/bin/activate` do not work. Windows-only mitmproxy tests use `@pytest.mark.skipif(sys.platform != "win32")` — CI has a dedicated `pytest-windows` job so they run.

### Config
The `.env` file lives **inside** `native_app/`. List-valued settings (`API_FLOW_IGNORE_HOSTS`, `API_FLOW_CAPTURE_HOST_ALLOWLIST`, `API_FLOW_CAPTURE_PATH_ALLOWLIST`, `ALLOWED_HOSTS`) require **JSON array** syntax, e.g. `API_FLOW_IGNORE_HOSTS=["host1","host2"]`. CSV was removed in v0.4.0; an empty value (`FIELD=`) is invalid and fails at startup. `API_FLOW_REPLAYS_PER_PAIR` (default 1) controls how many normalized replays are kept per player pair — raise it for H2H fleet-breakdown history (linear DB growth).

Logging is configured by OS env vars read by `app/core/logging_setup.py`: `APP_LOG_PATH` overrides the log file (default `~/.pss_logger/pss_logger.log`), `APP_LOG_LEVEL` sets level (default `INFO`). Each startup records `version`, `git_sha`, `build_time` as `event=build_info` in the log.

## High-level architecture

### Entry & lifecycle (`app/main.py`)
`main()` resolves the DB path via `configure_environment()` (defaults to `~/.pss_logger/pss_logger.db`, overridable with `DATABASE_URL`), initializes SQLite schema + indexes, then starts capture failure-tolerantly via `ApiFlowRuntime.start_capture()` before launching `CliManager`. Capture failures are logged and the CLI continues without capture. Daemon mode (`--daemon start|stop|status`) runs capture only, no interactive menu.

### Data pipeline
```
mitmproxy addon (app/services/mitm_api_flow_addon.py)
  → stdout JSON lines prefixed "API_FLOW_EVENT "
  → ApiFlowCaptureManager (spawns mitmdump, parses lines)
  → ApiFlowRuntime (in-memory queue, flush thread, retention purge)
  → ApiFlowRepository.save_events() → api_flow_events table
  → same-call normalization → battle_replays_normalized + battle_replay_{ships,rooms,characters,commands}
  → player_matchup_logs / player_matchup_stats (H2H stats) + prune of obsolete replays
```
Capture is scoped by `API_FLOW_CAPTURE_HOST_ALLOWLIST` / `API_FLOW_CAPTURE_PATH_ALLOWLIST` (default: `api.pixelstarships.com` + `/BattleService/GetBattle3`) and `API_FLOW_IGNORE_HOSTS` (Unity telemetry hosts are passthrough). `MITMPROXY_MODE=transparent` adds `--mode transparent` for on-device iptables capture (issue #46); any other value fails at startup. Sensitive headers are redacted before storage; response bodies are XML→JSON cleaned into `response_body_cleaned`.

### Layers
| Layer | Responsibility |
|-------|----------------|
| `app/main.py` | Entry, env config, DB init, capture bootstrap, CLI launch |
| `app/core/config.py` | Pydantic `Settings` (env + `.env`, JSON-array hinted decoding) |
| `app/core/logging_setup.py` | Rotating file log, `APP_LOG_PATH` / `APP_LOG_LEVEL` |
| `app/core/build_info.py` | Version/git SHA from embedded build metadata |
| `app/models/database.py` | SQLAlchemy engine/session, `Base`, schema migrations (`ensure_sqlite_schema`), indexes |
| `app/models/pss_models.py` | SQLAlchemy ORM models (ApiFlowEvent, BattleReplay*, PlayerMatchup*, design tables) |
| `app/dto/api_flow_dto.py` | Captured-flow DTOs |
| `app/services/api_flow_capture.py` | `ApiFlowCaptureManager` — spawns mitmdump with the addon, SHA-256 integrity check, trusted-binary allowlist |
| `app/services/api_flow_runtime.py` | `ApiFlowRuntime` — queue, flush, startup sync (backfill cleaned bodies → sync replays → sync children → backfill rooms → matchup backfill + prune) |
| `app/services/api_flow_storage.py` | `ApiFlowRepository` — CRUD, purge by TTL/size, battle replay extraction from cleaned XML, design catalog sync, matchup stats recompute |
| `app/services/api_flow_list_service.py` | Paginated listing, H2H report data, battle detail |
| `app/services/battle_detail_cache.py` | In-memory cache behind battle detail |
| `app/services/api_flow_h2h.py`, `catalogo.py`, `room_item_mapping.py`, `*_inspector_resolver.py`, `text_cleaning.py` | H2H stats, design/item catalogs, room slot resolution, inspectors, payload cleaning |
| `app/services/mitm_api_flow_addon.py` | mitmproxy addon that emits captured API flows as JSON to stdout |
| `app/cli/cli_manager.py` | Rich menu, 9 commands |
| `app/cli/concrete_commands.py` | Command implementations (query, reports, H2H, inspectors, capture, monitor, settings) |
| `app/cli/cli_services.py` | Service wrappers over list service + catalog resolvers for the CLI |
| `app/tui/app.py` | Textual app for `--tui`: dashboard (live capture state), paginated/searchable battle explorer; slow work in workers |
| `app/tui/screens.py` | Battle detail screen (ships / rooms / crew), loaded inside the app |
| `app/reporting/` | Excel/CSV/JSON report generators + templates |
| `app/resources/room_item_slot_mappings.json` | Slot name resolution used by the room inspector |
| `app/daemon_manager.py` | Background capture daemon |
| `scripts/build.sh`, `build.ps1`, `package_portable.py` | PyInstaller build → portable ZIP |

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

### CI/CD (`.github/workflows/`)
| Trigger | Workflow | Notes |
|---------|----------|-------|
| PR/push → `develop` | `native-tests.yml` | Ruff check + format and pytest on Linux **and** Windows |
| PR → `main` | `native-build.yml` | Linux + Windows PyInstaller builds + pytest |
| PR/push `develop`, `main` | `secret-scan.yml` | Gitleaks |
| Tag `v*` | `release.yml` | Stable release: portable ZIPs + SHA256SUMS |
| ~~Push `develop`~~ | `prerelease-develop.yml.disabled` | **Disabled** — no develop pre-releases |

### Key gotchas
- **DB path**: defaults to `~/.pss_logger/pss_logger.db` (created by `configure_environment()`).
- **Addon SHA**: `EXPECTED_MITM_ADDON_SHA256` in `api_flow_capture.py` must match `mitm_api_flow_addon.py` or the build/capture fails.
- **Line endings**: `.gitattributes` enforces LF for `.py` files.
- **Version**: single source in `pyproject.toml` (currently `0.4.0`); release number derives from the git tag `vX.Y.Z` — keep tag and pyproject aligned.
- **No GUI**: legacy Qt UI was removed; CLI-only via Rich plus optional Textual TUI. Don't resurrect Qt references.
- **Tests**: run from `native_app/`; fixtures use `tmp_path` and mock `ApiFlowRepository`.
- **Before a PR**: run both ruff commands — CI enforces them on both OSes.
- **Branching** (process, not branch protection): `develop` = integration, `main` = stable; all changes via PR to `develop`; stable release = PR `develop → main` → tag `vX.Y.Z` on `main`. See `docs/TEMP_GOVERNANCE_PROTOCOL.md`.
