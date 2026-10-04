# Agent Knowledge Base — Logger PSS

> **Purpose:** compact, operational context for AI coding agents working on `ruuuberth/cli-logger-pss`.
> This document is a companion to `AGENTS.md` and `docs/CODEBASE_ONBOARDING.md`. It should be updated when architecture, invariants, commands, or development workflow change.

## 1. Project identity

**Logger PSS** is a CLI application for capturing and analyzing Pixel Starships battle traffic. The application captures `BattleService/GetBattle3` responses through mitmproxy, persists raw/clean payloads, normalizes battle replays into relational SQLite tables, and exposes CLI inspection and reporting workflows.

Primary runtime entry point:

```text
native_app/app/main.py
```

Installed console command:

```text
pss-native
```

Current Python requirement and core dependencies are defined in `native_app/pyproject.toml`.

## 2. Source-of-truth hierarchy

When sources disagree, prefer them in this order:

1. Current executable code and tests.
2. `AGENTS.md` for agent-specific rules.
3. `docs/CODEBASE_ONBOARDING.md` for architecture/onboarding.
4. This knowledge base for consolidated operational context.
5. README and other descriptive documentation.

Never assume a historical README description is still true without checking the implementation.

## 3. Architecture at a glance

```text
pss-native
  -> app.main.main()
     -> configure_environment()
     -> database initialization
     -> ApiFlowRuntime.start_capture()
     -> CLI/application manager

Network path:

Pixel Starships
  -> mitmproxy
  -> mitm_api_flow_addon.py
  -> ApiFlowCaptureManager
  -> ApiFlowRuntime queue/backlog
  -> ApiFlowRepository
  -> api_flow_events
  -> same-flow normalization
  -> battle_replays_normalized
       |- battle_replay_ships
       |- battle_replay_rooms
       |- battle_replay_characters
       `- battle_replay_commands
  -> player_matchup_logs / player_matchup_stats
```

### Core responsibilities

| Component | Responsibility |
|---|---|
| `app/main.py` | Process entry point, environment, DB initialization, build/log setup |
| `app/core/config.py` | Pydantic settings and environment loading |
| `app/core/build_info.py` | Build version/Git SHA metadata |
| `app/services/mitm_api_flow_addon.py` | mitmproxy-side filtering/capture |
| `app/services/api_flow_capture.py` | Capture manager and addon output handling |
| `app/services/api_flow_runtime.py` | Runtime orchestration, queue, flush, persistence coordination |
| `app/services/api_flow_storage.py` | Persistence and battle normalization |
| `app/services/api_flow_list_service.py` | Main event listing/pagination/read model |
| `app/services/battle_detail_cache.py` | Cache for recently inspected battle details |
| `app/services/perf_metrics.py` | Lightweight performance measurements |
| `app/services/process_resource_monitor.py` | CPU/RAM/process resource monitoring |
| `app/models/pss_models.py` | SQLAlchemy models/tables |
| `app/cli/*` | CLI manager, commands, and service wrappers |
| `app/reporting/*` | XLSX/CSV/JSON reporting |

> La capa `app/ui/*` fue eliminada junto con la UI Qt. La presentación es la consola Rich (`app/cli/*`); no reintroducir UI frameworks.

## 4. Architectural invariants

Agents MUST preserve these unless a task explicitly changes the architecture:

- `MainWindow`/UI code no longer exists: the Qt UI was removed. Presentation lives in `app/cli/*` and must not contain network parsing, persistence, or capture orchestration.
- `ApiFlowRuntime` is the boundary that knows both capture and repository layers.
- Capture filtering belongs in the mitmproxy addon, not in the CLI.
- Preserve replay data: normalization must not silently discard fields that may be useful for future inspection.
- Local catalogs are the primary source for inspector translations; API catalog synchronization is a fallback/update path.
- H2H pair identity is unordered: `(A,B)` and `(B,A)` represent the same pair.
- H2H insertion updates the minimal matchup log, prunes obsolete replay data for the pair, and recalculates aggregate stats.
- Retention keeps the N most recent replays per pair **counting distinct battles** (`API_FLOW_REPLAYS_PER_PAIR`, default 1); duplicate captures of the same battle never waste a retention slot.
- Individual event deletion must keep replay data and H2H aggregates consistent.
- Retention/TTL logic must preserve referential and cross-table consistency.

## 5. Database model

Default local database locations:

```text
~/.pss_logger/pss_logger.db
```

Development/runtime variants may use:

```text
native_app/pss_logger_dev.db
native_app/pss_logger.db
```

Important tables:

- `api_flow_events` — captured event/raw-clean payload record.
- `battle_replays_normalized` — normalized battle/replay root.
- `battle_replay_ships` — normalized ship data.
- `battle_replay_rooms` — normalized room data.
- `battle_replay_characters` — normalized crew/character data.
- `battle_replay_commands` — normalized command/action data.
- `player_matchup_logs` — minimal H2H history.
- `player_matchup_stats` — aggregate H2H statistics.
- Catalog tables include ship, room, and crew design data where applicable.

Before changing a model, search all readers/writers, migration scripts, reports, and tests that reference the table.

## 6. Capture configuration

Configuration lives in `native_app/.env` for local runs. Do not commit real `.env` files.

Important settings:

```text
API_FLOW_ENABLED=true
MITMPROXY_BINARY=mitmdump
MITMPROXY_LISTEN_HOST=127.0.0.1
MITMPROXY_LISTEN_PORT=8081
API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"]
API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"]
API_FLOW_IGNORE_HOSTS=["..."]
```

JSON arrays are the preferred list format. CSV list syntax exists only for compatibility and is deprecated.

The intended narrow capture target is the Pixel Starships battle endpoint. Avoid broadening capture filters unless the task requires it.

## 7. Development commands

### Linux/macOS

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pytest -q
python -m pytest -q
pss-native
```

### Windows

```powershell
cd native_app
python -m venv .venv
.venv/Scripts/pip install -e .
.venv/Scripts/python.exe -m pytest
.venv/Scripts/pss-native
```

Build scripts:

```text
native_app/scripts/build.sh
native_app/scripts/build.ps1
```

Migration example:

```bash
python scripts/migrate_battle_replays_normalized.py
```

## 8. Testing strategy

Run the full test suite after behavioral changes:

```bash
cd native_app
python -m pytest -q
```

For focused work, run the smallest relevant test module first, then the full suite.

Important test areas include:

- capture/addon behavior
- normalization/persistence
- build metadata
- configuration
- H2H accounting
- CLI command behavior
- reporting

Do not remove or weaken tests merely to make a failing implementation pass. Fix the implementation or update the test only when the intended behavior has deliberately changed.

## 9. Common traps

### Addon hash
`api_flow_capture.py` protects the expected mitmproxy addon content with `EXPECTED_MITM_ADDON_SHA256`. If `mitm_api_flow_addon.py` changes, the expected hash must be updated as part of the intentional change.

### Database path
Do not hard-code the DB location in services. Use the configured/environment-resolved path.

### Secrets
Only example environment files belong in Git. Secret scanning runs in CI. Never add tokens, credentials, private cookies, or real `.env` contents to the repository.

### Windows execution
Do not assume `python3`, `source`, or Unix `.venv/bin/*` paths on Windows. Use `.venv/Scripts/*`.

### UI performance
No aplica: la UI Qt fue eliminada. La CLI es liviana por diseño; si el listado crece, mantener la paginación existente en `api_flow_list_service.py` y los caches (`battle_detail_cache`).

### Replay loss
When parsing an API response, unknown fields should generally be retained in the raw/clean payload even if they are not yet normalized into a dedicated table.

## 10. Agent workflow

Before editing:

1. Read `AGENTS.md`.
2. Read `docs/CODEBASE_ONBOARDING.md`.
3. Identify the owning layer/component.
4. Search for callers and consumers before changing an API/model.
5. Inspect existing tests for the behavior being changed.
6. Check whether a migration or compatibility path is required.

While editing:

1. Make the smallest coherent change.
2. Preserve public behavior unless the task requests a breaking change.
3. Keep parsing, persistence, CLI presentation, and orchestration responsibilities separated.
4. Add/update tests for new behavior and regressions.
5. Do not mix unrelated refactors into a bug fix.

After editing:

1. Run focused tests.
2. Run the full test suite when practical.
3. Check formatting/import errors and packaging/build implications.
4. Review the diff for accidental changes, secrets, generated artifacts, and debug code.
5. Update documentation when architecture/configuration/workflow changed.

## 11. Change-impact map

Use this as a first-pass routing guide:

| Task | Start here | Also inspect |
|---|---|---|
| Capture/filtering | `services/mitm_api_flow_addon.py` | capture tests, runtime, hash check |
| Capture orchestration | `services/api_flow_runtime.py` | capture/storage tests |
| Persistence | `services/api_flow_storage.py` | models, migrations, DB tests |
| New replay field | parser/storage + `models/pss_models.py` | inspectors, reports, tests |
| H2H bug | matchup methods in storage | logs, stats, deletion/retention tests |
| Listing/pagination | `services/api_flow_list_service.py` | CLI query command, query tests |
| Inspector behavior | corresponding CLI inspector command | model/schema/parser tests |
| CLI command | `app/cli/concrete_commands.py` | `cli_manager.py`, CLI services, tests |
| Config | `app/core/config.py` | `.env.example`, tests, docs |
| Reporting | `app/reporting/` | CLI commands, XLSX/CSV/JSON tests |
| Build/release | `scripts/build.*`, workflows | `pyproject.toml`, build-info tests |

## 12. Release and branch policy

```text
develop = integration/development
main    = stable releases
```

Normal features/fixes go through PRs into `develop`. Stable releases are promoted from `develop` to `main` and tagged `vX.Y.Z`.

Portable release assets are ZIPs for Linux/Windows; loose binaries are not the intended release format.

## 13. Useful search patterns for agents

When navigating the codebase, search for exact symbols before guessing file locations:

```text
ApiFlowRuntime
ApiFlowCaptureManager
ApiFlowRepository
EXPECTED_MITM_ADDON_SHA256
battle_replays_normalized
player_matchup_logs
player_matchup_stats
CharacterActionsNormalized
CharacterItemsNormalized
room_item_slot_mappings
API_FLOW_CAPTURE_HOST_ALLOWLIST
API_FLOW_CAPTURE_PATH_ALLOWLIST
```

## 14. Definition of done

A change is normally complete when:

- the implementation is in the correct architectural layer;
- existing invariants remain true;
- regression/new tests cover the changed behavior;
- the full relevant test suite passes;
- configuration/migrations/build artifacts are handled if affected;
- documentation is updated when behavior or architecture changed;
- no secrets or generated local artifacts are committed;
- the final diff is limited to the requested work.
