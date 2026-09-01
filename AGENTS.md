# AGENTS.md — Logger PSS CLI

**Project**: Pixel Starships battle capture & analysis CLI  
**Stack**: Python 3.11+, mitmproxy, SQLAlchemy, Rich, PyInstaller  
**Entry point**: `pss-native` (native_app/app/main.py)

---

## Quick Commands (Windows)

```bash
# Setup
cd native_app && python -m venv .venv && .venv/Scripts/pip install -e .

# Run tests (125 tests, ~6s)
.venv/Scripts/python.exe -m pytest

# Single test
.venv/Scripts/python.exe -m pytest tests/test_api_flow_capture.py

# Run app
.venv/Scripts/pss-native

# Build
./scripts/build.sh        # Linux
./scripts/build.ps1       # Windows (PowerShell)

# Config
cp ../.env.dev.example .env   # .env lives INSIDE native_app/
```

⚠️ **Windows only**: Use `.venv/Scripts/python.exe` — `python3` and `source .venv/bin/activate` do NOT work.

---

## Architecture (Key Flow)

```
main.py
  → configure_environment()  # resolves DB path (~/.pss_logger/pss_logger.db)
  → ApiFlowRuntime.start_capture()  # failure-tolerant, runs before CLI
  → CliManager interactive menu (7 commands)
```

**Data pipeline**: mitmproxy addon → stdout JSON → ApiFlowCaptureManager → ApiFlowRuntime (queue) → ApiFlowRepository.save_events() → `api_flow_events` → **same-call normalization** → `battle_replay_*` tables → H2H matchup log/stats.

---

## Project Structure

```
native_app/
├── app/
│   ├── main.py              # Entry point, build info, logging, DB init
│   ├── cli/
│   │   ├── cli_manager.py   # Menu + 7 command handlers
│   │   ├── concrete_commands.py  # QueryEvents, GenerateReport, InspectChar, InspectRoom, InspectBattle, CaptureTraffic, SystemMonitor, Settings
│   │   └── cli_services.py  # Qt-free wrappers over services
│   ├── core/
│   │   ├── config.py        # Pydantic Settings (env + .env)
│   │   └── build_info.py    # Version/git SHA from embedded metadata
│   ├── models/pss_models.py # All SQLAlchemy tables
│   ├── services/            # Capture, storage, list, inspectors, catalogs
│   └── reporting/           # Excel/CSV/JSON generators
├── scripts/build.sh|.ps1    # PyInstaller one-file → portable ZIP
├── tests/                   # 125 tests (pytest)
└── pyproject.toml           # deps, scripts, pytest config
```

---

## Key Config (`.env` inside `native_app/`)

| Variable | Purpose |
|----------|---------|
| `API_FLOW_ENABLED` | Enable capture (default true) |
| `MITMPROXY_BINARY` | `mitmdump` or full path |
| `MITMPROXY_LISTEN_HOST/PORT` | Proxy bind (default 127.0.0.1:8081) |
| `API_FLOW_CAPTURE_HOST_ALLOWLIST` | JSON array, e.g. `["api.pixelstarships.com"]` |
| `API_FLOW_CAPTURE_PATH_ALLOWLIST` | JSON array, e.g. `["/BattleService/GetBattle3"]` |
| `API_FLOW_IGNORE_HOSTS` | JSON array of hosts to skip |
| `CLI_FORCE_ASCII` | Force ASCII output (Windows legacy) |

List values: **JSON array format preferred** (CSV deprecated).

---

## CI/CD (`.github/workflows/`)

| Trigger | Workflow | Notes |
|---------|----------|-------|
| PR → `main` | `native-build.yml` | Linux + Windows build + pytest (capture/build_info) |
| Tag `v*` | `release.yml` | Stable release: portable ZIPs + SHA256SUMS |
| Push `develop` | `prerelease-develop.yml.disabled` | **Disabled** |
| Any | `secret-scan.yml` | Gitleaks on `develop`/`main` |

**Release assets**: portable ZIPs only (no loose binaries). Build fails if `EXPECTED_MITM_ADDON_SHA256` in `api_flow_capture.py` mismatches `mitm_api_flow_addon.py`.

---

## Branching (no branch protection — enforced by process)

- `develop` = integration branch
- `main` = stable releases
- All changes via PR to `develop`
- Stable release: PR `develop → main` → tag `vX.Y.Z` on `main`
- See `docs/TEMP_GOVERNANCE_PROTOCOL.md` for full rules

---

## Testing Notes

- `pythonpath = ["."]` in pyproject.toml → run from `native_app/`
- Tests use `tmp_path` fixtures, mock `ApiFlowRepository`
- Windows-specific mitmproxy tests marked `@pytest.mark.skipif(sys.platform != "win32")`

---

## Common Gotchas

1. **DB path**: Defaults to `~/.pss_logger/pss_logger.db` (created by `configure_environment()`)
2. **Addon SHA**: Update `EXPECTED_MITM_ADDON_SHA256` in `api_flow_capture.py` when `mitm_api_flow_addon.py` changes
3. **Line endings**: `.gitattributes` enforces LF for `.py` files
4. **Version**: Single source in `pyproject.toml` (currently `0.1.3`); embedded in build metadata at compile time
5. **No GUI code**: Legacy Qt UI removed; `docs/NATIVE_ROADMAP.md` deleted (uncommitted)

---

## MCP Codebase Memory

- Graph project: `C-Users-Administrador-Proyectos-Ruberth-CLI`
- Use `search_graph`, `trace_path`, `get_code_snippet` for code discovery
- `check_index_coverage` before claiming completeness
