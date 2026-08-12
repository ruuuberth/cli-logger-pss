# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Logger PSS** is a command-line interface (CLI) application for analyzing Pixel Starships battles from network traffic. It captures battle responses (`GetBattle3`) using mitmproxy, normalizes data into relational tables, and provides CLI commands for battle reporting and data export.

**Note:** This project is being migrated from a GUI version. You may find legacy references to UI components (Qt, PyQt6, MainWindow, etc.) in the codebase. These are being phased out in favor of CLI-only functionality. The GUI version exists as a separate repository.

## Development Setup

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .
cp ../.env.dev.example .env
```

Run the application:
```bash
pss-native
# or
python -m app.main
```

## Build Commands

**Build portable binaries:**
```bash
cd native_app
./scripts/build.sh           # Linux
./scripts/build.ps1          # Windows
```

Output: `native_app/dist/pss-logger-native-{linux|windows}-portable.zip`

**Run tests:**
```bash
cd native_app
pytest -q
python -m pytest -q tests/test_api_flow_capture.py tests/test_build_info.py
```

**Database migration (backfill historical data):**
```bash
cd native_app
python scripts/migrate_battle_replays_normalized.py
```

**Generate battle reports (CLI):**
```bash
python -c "from app.cli.concrete_commands import GenerateBattleReportCommand; GenerateBattleReportCommand().execute(['--non-interactive','--format=excel','--output-dir=./native_app/reports','--filename=Reporte_Batallas_Test','--no-timestamp'])"
```

## Architecture

### Core Components

**CLI Layer:**
- `app/cli/cli_manager.py` - Main CLI menu and command dispatcher
- `app/cli/concrete_commands.py` - Command implementations (reports, queries, etc.)

**Services Layer:**
- `app/services/api_flow_runtime.py` - Capture coordinator (backlog, flush, startup sync)
- `app/services/api_flow_capture.py` - Capture runtime manager
- `app/services/api_flow_storage.py` - Persistence and normalization
- `app/services/mitm_api_flow_addon.py` - mitmproxy addon

**Core:**
- `app/core/config.py` - Configuration (env vars with defaults)
- `app/core/build_info.py` - Build metadata (version, git SHA, build time)
- `app/models/pss_models.py` - SQLAlchemy models
- `app/main.py` - Application entry point

### Data Flow

1. Traffic captured via mitmproxy proxy
2. Passthrough applied for hosts in `API_FLOW_IGNORE_HOSTS`
3. `ApiFlowRuntime` maintains backlog, periodic flush, and final flush
4. Event saved to `api_flow_events`
5. Payload cleaned in `response_body_cleaned`
6. Replay normalized to relational tables
7. Design catalogs synced (`ship_designs`, `room_designs`, `crew_designs`) from `/DesignService/ListAllStaticDesigns2`
8. CLI commands query normalized data for reports and analysis
9. H2H cycle applied per player pair: minimal logger + stats + obsolete replay pruning

### Database Schema

**Replay Tables:**
- `battle_replays_normalized` - Main battle metadata
- `battle_replay_ships` - Ship details per battle
- `battle_replay_rooms` - Room details per battle
- `battle_replay_characters` - Character details per battle
- `battle_replay_commands` - Commands executed during battle
- `player_matchup_logs` - Minimal H2H logger per battle
- `player_matchup_stats` - Aggregated H2H stats per player pair

**H2H (Head-to-Head) Policy:**
- Canonical pair key: `(min(attacker_user_id, defender_user_id), max(...))`
- Only 1 replay kept per pair (most recent by `captured_at/id`)
- Mini H2H logger stores winner by `battle_id` without duplicates per pair
- H2H summary recalculated from logger and exported in CLI reports
- TTL/size purge removes old replay but preserves logger/summary

### Performance Considerations

- Batch processing of network captures reduces I/O overhead
- Lighter queries avoid materializing full ORM rows when unnecessary
- Battle detail cache avoids recomputing full serialization for repeated queries
- Normalized schema enables efficient SQL queries for reporting

## Key Responsibilities

- `CliManager` orchestrates the interactive CLI menu and command execution
- `ApiFlowRuntime` is the only layer that knows both `ApiFlowCaptureManager` and `ApiFlowRepository`
- `ApiFlowStorage` handles persistence and normalization of battle data
- Commands in `concrete_commands.py` handle report generation and data export

## Environment Variables

Configuration via `.env` (optional, defaults exist):

**Capture:**
- `API_FLOW_ENABLED` - Enable/disable capture
- `MITMPROXY_BINARY` - Path to mitmdump
- `MITMPROXY_LISTEN_HOST` - Proxy host (default: 127.0.0.1)
- `MITMPROXY_LISTEN_PORT` - Proxy port (default: 8081)

**Filtering:**
- `API_FLOW_IGNORE_HOSTS` - JSON array of hosts to passthrough
- `API_FLOW_CAPTURE_HOST_ALLOWLIST` - JSON array: `["api.pixelstarships.com"]`
- `API_FLOW_CAPTURE_PATH_ALLOWLIST` - JSON array: `["/BattleService/GetBattle3"]`

**Storage:**
- `API_FLOW_BODY_MAX_CHARS` - Max chars per response body
- `API_FLOW_RETENTION_DAYS` - Days to keep events
- `API_FLOW_MAX_DB_MB` - Max database size in MB

**Logging:**
- `APP_LOG_PATH` - Full path to log file
- `APP_LOG_LEVEL` - Log level (INFO, DEBUG, WARNING, etc.)

**Reports:**
- `REPORT_OUTPUT_DIR` - Default output directory
- `REPORT_DEFAULT_FORMAT` - excel|csv|json
- `REPORT_INCLUDE_TIMESTAMP` - true|false

**List format:** JSON arrays recommended (e.g., `["host1","host2"]`). CSV format (`host1,host2`) is deprecated.

## Git Workflow

**Branch Strategy:**
- `develop` - Development and integration
- `main` - Stable production
- Feature/fix branches: `feat/<topic>`, `fix/<topic>`, `refactor/<topic>`, `docs/<topic>`, `chore/<topic>`

**Important Rules:**
- All changes MUST go through PRs to `develop`
- NO direct pushes to `develop` or `main` (operational rule enforced by team, not GitHub branch protection)
- See `docs/TEMP_GOVERNANCE_PROTOCOL.md` for temporary governance protocol

**Expected Flow:**
1. `git checkout develop && git pull --ff-only`
2. Create feature branch
3. Implement changes + local tests
4. Update docs if behavior changes
5. Open PR with single scope

## CI/CD

**Workflow Strategy:**
Binary builds and releases are triggered only when merging `develop` → `main`, ensuring stable releases go through proper testing on the develop branch first.

**PR to `develop`:**
- No binary build runs (only secret-scan runs on develop)
- PRs target `main` for build verification via `Native Build`

**Merge `develop` → `main`:**
- Triggers `Native Release` workflow
- Auto-generates versioned tag `vYYYY.MM.DD-<short_sha>` (or `vYYYY.MM.DD-HHMMSS-<short_sha>` on same-day collision)
- Builds Linux + Windows binaries and publishes as stable release
- Attaches portable ZIPs + `SHA256SUMS.txt` (+ optional signature)

**Push tag `v*`:**
- Alternative trigger for stable releases
- Uses the tag name directly as release version
- Use for manually versioned releases

**Secret Scan (gitleaks):**
- Runs on both `develop` and `main` (PRs and pushes)
- Only CI/CD that triggers on `develop` changes

**Binary Policy:**
- Only portable ZIPs are published (NOT loose binaries)
- Build fails if executable doesn't contain mitmproxy addon diagnostic markers
- Each ZIP includes: executable, mitmproxy runtime, README_RUNTIME.txt, THIRD_PARTY_NOTICES.txt

**Optional Signing:**
- If `SIGNING_PRIVATE_KEY` (+ optional `SIGNING_PASSPHRASE`) exist, signs `SHA256SUMS.txt` as `SHA256SUMS.txt.asc`
- Release continues without failure if secrets don't exist

## Important Conventions

- Parser must prioritize not losing replay data
- Capture filter applies in mitmproxy addon
- TTL/size retention must maintain coherence between tables
- CLI commands must handle errors gracefully and provide clear user feedback
- Report generation should support multiple formats (excel, csv, json)

## Database Locations

**Development:**
- With `.env.dev.example`: `sqlite:///./pss_logger_dev.db`
- File: `native_app/pss_logger_dev.db`

**Production:**
- Linux: `~/.pss_logger/pss_logger.db`
- Logs: `~/.pss_logger/pss_logger.log`

Each startup logs active build (`version`, `git_sha`, `build_time`) for support verification.

## Security

- Never commit real `.env` files
- Only `.env.example` and `.env.dev.example` allowed
- Secret scan (`gitleaks`) runs on `develop` and `main`

## Documentation

- `native_app/README.md` - Technical module details
- `docs/CODEBASE_ONBOARDING.md` - Technical onboarding
- `docs/TEMP_GOVERNANCE_PROTOCOL.md` - Temporary governance protocol (no branch protection)
- `CONTRIBUTING.md` - Contribution guidelines
