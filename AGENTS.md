<!-- codebase-memory-mcp:start -->
# Codebase Memory

## Codebase Knowledge Graph (codebase-memory-mcp)

This project uses codebase-memory-mcp to maintain a knowledge graph of the codebase.
ALWAYS use MCP graph tools FIRST for ANY code discovery or source reading. `read`/`grep`/`glob` are LAST RESORT only.

### Priority Order
1. `search_graph` — find functions, classes, routes, variables by pattern
2. `trace_path` — trace who calls a function or what it calls
3. `get_code_snippet` — read specific function/class source code
4. `check_index_coverage` — validate candidate paths and missed ranges before claims
5. `query_graph` — run Cypher queries for complex patterns
6. `get_architecture` — high-level project summary

### Evidence tiers
- **Scout (Tier 1):** quick positive lookup with few calls and targeted source checks. Mark it provisional; do not make negative or exhaustive claims.
- **Verify (Tier 2, default):** task-directed graph evidence, relevant trace directions, exact snippets for material claims, and relevant pagination.
- **Auditor (Tier 3):** bounded-scope full verification with current generation, complete relevant pagination, both call directions and broader relationships when material, and every limitation disclosed.
- After candidate paths are known in any tier, call `check_index_coverage` once with every evidence path. Add relevant scopes for negative or exhaustive claims. A clean result means no recorded gap, not proof of completeness. For partial, skipped, excluded, stale, pending, or unknown coverage, read/grep the reported ranges or scope before relying on graph results.

### Fallback to filesystem tools (read/grep/glob) — LAST RESORT
Try MCP first. Use filesystem tools ONLY when MCP cannot answer:
- Searching for string literals, error messages, config values
- Searching non-code files (Dockerfiles, shell scripts, configs)
- When MCP tools return insufficient results (including reading missed-coverage ranges reported by `check_index_coverage`)

### Project-Specific Guidance
- **Graph project name**: `C-Users-Administrador-Proyectos-Ruberth-CLI` (see `list_projects`)
- **Main Application**: `native_app/app/main.py` - Entry point (`pss-native` command)
- **Configuration**: `native_app/pyproject.toml` - Dependencies, scripts, pytest config
- **Build Scripts**: `native_app/scripts/build.sh` (Linux) and `build.ps1` (Windows)
- **Tests**: `native_app/tests/` - 116 tests, all passing
- **DB models**: `native_app/app/models/pss_models.py` (all SQLAlchemy tables)

### Session resets and subagents
- At session start or after compaction, confirm the nearest graph project and generation with `list_projects` or `index_status`, then choose Scout, Verify, or Auditor.
- Before spawning a subagent, query the graph and coverage in the parent. Pass the tier, project, generation/freshness, bounded scope, queries and pagination state, qualified symbols, paths, call-chain findings, coverage evidence with ranges/reasons, source fallback already performed, and unresolved questions in the delegated task context.
- Do not assume subagents inherit MCP access or the parent conversation. If a child lacks MCP tools, it must not call or claim MCP access. It should use the supplied evidence and read/grep exact source, especially every reported missed-coverage range.

## Skills (check BEFORE executing tasks)

This machine has a large skills catalog. Before starting any task, check if a skill matches — invoke it via the `skill` tool:
- **Catalog**: `~/.config/opencode/skills/` — 200+ specialized skills (python-pro, test-master, debugging-wizard, code-reviewer, security-reviewer, spec-miner, llm-wiki-bootstrap, ...)
- **Superpowers plugin**: process skills like `brainstorming` (before building features), `systematic-debugging` (before fixing bugs), `test-driven-development`, `writing-plans`, `verification-before-completion`
- **Rule**: if a skill's description matches the task, invoke it first — don't rationalize skipping it. If there is even a 1% chance it applies, use it.

## Project-Specific Commands (verified on this Windows machine)

### Setup & Development
- **Setup**: `cd native_app && python -m venv .venv && .venv/Scripts/pip install -e .`
- **Run tests**: `cd native_app && .venv/Scripts/python.exe -m pytest` (116 tests, ~6s)
- **Single test**: `.venv/Scripts/python.exe -m pytest tests/test_api_flow_capture.py`
- **Run app**: `.venv/Scripts/pss-native` (or `.venv/Scripts/python.exe run.py`)

⚠️ **`python3` and `source .venv/bin/activate` do NOT work here** — use `.venv/Scripts/python.exe` (Windows venv layout).

### Building & Packaging
- **Build Linux**: `cd native_app && ./scripts/build.sh`
- **Build Windows**: `cd native_app && ./scripts/build.ps1`
- PyInstaller one-file build; output: `native_app/dist/pss-logger-native-<platform>-portable.zip`

### Environment Configuration
- Copy example: `cp .env.dev.example native_app/.env` (the `.env` lives INSIDE `native_app/`)
- Never commit real `.env` files; only `*.example` files are allowed
- Key vars: `API_FLOW_ENABLED`, `MITMPROXY_BINARY`, `MITMPROXY_LISTEN_HOST/PORT`, `API_FLOW_CAPTURE_HOST_ALLOWLIST`, `API_FLOW_CAPTURE_PATH_ALLOWLIST`, `API_FLOW_IGNORE_HOSTS`
- List values: JSON array format preferred (CSV deprecated)

### CI/CD (actual triggers — read before claiming)
- **PR to `main` only** → `native-build.yml` (Linux + Windows build + pytest on capture/build_info tests)
- `prerelease-develop.yml.disabled` — pre-release workflow is **disabled**
- Tag `v*` → stable release with portable ZIPs only (no loose binaries)
- Secret scan (`gitleaks`) on `develop`/`main`

## Architecture (non-obvious flow)

### Startup & capture pipeline
`main.py` → `configure_environment()` (resolves DB path, default `~/.pss_logger/pss_logger.db`) → starts capture **before** the CLI (failure-tolerant: CLI runs even if mitmproxy fails) → `CliManager` interactive menu.

Data pipeline: mitmproxy runs `app/services/mitm_api_flow_addon.py` → addon prints `API_FLOW_EVENT <json>` lines to stdout → `ApiFlowCaptureManager._read_stdout()` parses → `ApiFlowRuntime.enqueue_event()` (pending queue) → `flush_pending()` → `ApiFlowRepository.save_events()` → `api_flow_events` table → **normalization in the same call** (`_build_battle_replay_rows` + `_build_battle_replay_child_rows`) → `battle_replay_*` tables → H2H matchup log/stats.

### CLI structure
- `app/cli/concrete_commands.py` — 7 commands; `app/cli/cli_services.py` — Qt-free service wrappers
- `CharacterCliService` / `RoomCliService` resolve characters/rooms from `get_battle_detail()` via `CharacterInspectorResolver` and `BattleInspectorResolver`+`RoomItemMappingResolver`. `InspectBattleCommand` prints a raw dict dump (no table rendering).

### Gotchas
- **`EXPECTED_MITM_ADDON_SHA256`** in `api_flow_capture.py` must be updated whenever `mitm_api_flow_addon.py` changes — the build fails on SHA mismatch (normalized to LF).
- `pyrightconfig.json` and `opencode.json` are gitignored.
- `docs/NATIVE_ROADMAP.md` is deleted in the worktree (uncommitted) — do not reference it as current docs.

## Knowledge Base

This project has an associated Obsidian vault as a persistent knowledge base, maintained by the LLM using the LLM-Wiki pattern (see `[[karpathy/llm-wiki]]` in the vault). The vault is located at `[VAULT_PATH]` (replace with actual path).

- **Vault schema**: `AGENTS.md` (in the vault root) — defines how the LLM maintains the wiki.
- **How to use**: At the start of any session, read the vault's `index.md` and `90-meta/convenciones-de-pagina.md` before interacting with the wiki.
- **To ingest a new source**: follow the "Ingest" workflow in the vault's `AGENTS.md`.
- **To bootstrap a new wiki for another project**: use the skill `llm-wiki-bootstrap` (available in `~/.config/opencode/skills/llm-wiki-bootstrap`).

Replace `[VAULT_PATH]` with the absolute or relative path to the vault directory.