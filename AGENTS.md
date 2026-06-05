# AGENTS.md — GUI-Logger-PSS

## Proyecto
App CLI nativa (español) para capturar e inspeccionar replays de batalla de **Pixel Starships** vía mitmproxy.  
**Todo el código activo está en `native_app/`.** La capa UI (`app/ui/`) es legacy — no mantener.

## Inicio rápido para agentes
- **Entrypoint:** `native_app/app/main.py:main()` → CLI interactiva via `CliManager`
- **Cwd:** siempre ejecutar comandos desde `native_app/`
- **Python:** ≥ 3.11 (obligatorio)
- **Dependencias clave:** mitmproxy 11.0.2, SQLAlchemy 2.0+, Pydantic 2.10+, Rich (CLI)

## Comandos (ejecutar desde `native_app/`)
- **Ejecutar:** `python run.py` o `pss-native` (si está instalado)
- **Test (todo):** `python -m pytest`
- **Test (archivo):** `python -m pytest tests/test_<name>.py`
- **Test (caso):** `python -m pytest tests/test_<name>.py::test_<specific>`
- **Reporte no interactivo:** `python -c "from app.cli.concrete_commands import GenerateBattleReportCommand; GenerateBattleReportCommand().execute(['--non-interactive','--format=excel','--output-dir=./native_app/reports','--filename=Reporte_Batallas_Test','--no-timestamp'])"`
- **Migración DB:** `python scripts/migrate_battle_replays_normalized.py`
- **Build Linux:** `./scripts/build.sh`
- **Instalar editable:** `pip install -e .`

## CI (GitHub Actions)
| Workflow | Trigger | Acción |
|----------|---------|--------|
| `native-build.yml` | PR a develop/main, manual | Build + solo corre `tests/test_api_flow_capture.py` |
| `prerelease-develop.yml` | Push a develop | Build + publica pre-release `develop-latest` (mueve tag forzado) |
| `release.yml` | Tag `v*` | Build + publica release estable (valida tag descendiente de origin/main) |
| `secret-scan.yml` | PR/push a develop/main | Gitleaks |

## Arquitectura
**Ver** [docs/CODEBASE_ONBOARDING.md](docs/CODEBASE_ONBOARDING.md) para detalles completos.

### Layers
- **CLI:** `app/cli/cli_manager.py` + `cli_services.py` + `concrete_commands.py` + `utils.py` (entrypoint principal y utilidades de UI)
- **Services:** Captura (`api_flow_capture.py`), Runtime (`api_flow_runtime.py`), Storage (`api_flow_storage.py`), Caché (`battle_detail_cache.py`)
- **Models/DB:** SQLAlchemy ORM en `app/models/` — mapeado a SQLite con WAL mode
- **Config:** `app/core/config.py` (Pydantic Settings, lee `.env` y defaults)
- **UI Legacy:** `app/ui/` — no mantener, es dead code

### Instanciación de servicios
- **Sin DI:** los servicios se crean directamente en `CliManager.__init__()`
- Patrón: cada comando es una clase que hereda de `AbstractCommand` y recibe sus servicios en `__init__`

### Base de datos
- **Tipo:** SQLite, default `~/.pss_logger/pss_logger.db` (directorio se auto-crea)
- **Setup:** `app/models/database.py` configura PRAGMA (WAL, foreign_keys, busy_timeout)
- **Engine:** `app.models.database.engine` + `SessionLocal()` factory
- **Modelos:** Replay (`BattleReplayNormalized`), Nave (`Ship`), Sala (`Room`), etc. en `pss_models.py`

## Pipeline de Datos
1. **Captura:** `mitmdump` → `api_flow_events`
2. **Limpieza:** `response_body_cleaned`
3. **Normalización:** Tablas replay (`battle_replays_normalized`, `ships`, `rooms`, `characters`, `commands`)
4. **Consolidación:** `player_matchup_logs` & `stats` (Policy H2H: 1 replay vigente por pareja)

## Recursos Críticos
- `app/resources/room_item_slot_mappings.json`: Mapeo manual de slots a nombres canónicos de items (crítico para el inspector de IA).


## Testing
- **Config:** pytest en `pyproject.toml` con `pythonpath = ["."]` — imports `app.xxx` funcionan desde `native_app/`
- **Suite:** Sin `conftest.py` ni `pytest.ini`, sin librerías mock (monkeypatch + stubs manuales)
- **Skip:** `test_main_startup_smoke.py` — skip completo (legacy GUI tests)
- **Trap:** Algunos tests crean `.env` temp — asegurar que `DATABASE_URL` no esté seteada antes de correr
- **Correr:** `python -m pytest tests/test_<name>.py::test_<specific>` (desde `native_app/`)

## Convenciones
- Python ≥ 3.11 obligatorio
- Listas en env vars: formato JSON array (canónico). CSV funciona pero deprecado con warning
- Logging: `%(asctime)s | %(levelname)s | %(name)s | %(message)s`, eventos estructurados `key=value`
- Sin linter/formatter configurado
- Sin branch protection; todo cambio entra por PR a `develop`
- Prefijos rama: `feat/`, `fix/`, `refactor/`, `docs/`, `chore/`
- PR target: `develop` (normal), `main` (solo promoción controlada)
- Code owner: @ruuuberth

## Build (PyInstaller)
```bash
pip install -U pip setuptools wheel && pip install -e . pyinstaller
pyinstaller --name pss-logger-native --windowed --onefile --paths . --collect-data app.services run.py
python scripts/package_portable.py --platform <linux|windows> --app-binary <dist/pss-logger-native> --output-dir dist
```
Output: `dist/pss-logger-native-<platform>-portable.zip` (incluye mitmproxy 11.0.2 runtime)  
Deps Linux CI: `libglib2.0-0 libgl1 libegl1 libxkbcommon-x11-0 libdbus-1-3`

## Development Setup

### Desarrollo rápido
```bash
cd native_app
python3.11 -m venv .venv
source .venv/bin/activate  # o: .venv\Scripts\activate en Windows
pip install -e .
python run.py
```

### Variables de entorno críticas
- `DATABASE_URL`: Ruta SQLite (default: `~/.pss_logger/pss_logger.db`)
- `APP_LOG_LEVEL`: DEBUG/INFO/WARNING (default: INFO)
- `API_FLOW_ENABLED`: true/false (default: true)
- `MITMPROXY_LISTEN_PORT`: 8081+ (default: 8081)
- `API_FLOW_CAPTURE_HOST_ALLOWLIST`: `["api.pixelstarships.com"]` (recomendado para rendimiento)
- `API_FLOW_CAPTURE_PATH_ALLOWLIST`: `["/BattleService/GetBattle3"]` (recomendado para rendimiento)

Ver `app/core/config.py` para lista completa de settings (Pydantic).

## Common Patterns

### Crear nuevo comando CLI
1. Heredar de `AbstractCommand` en `app/cli/commands.py`
2. Implementar `run(self)` con lógica
3. Registrar en `CliManager.__init__()` y menú (`_setup_menus()`)
4. Usar servicios inyectados: `self.api_flow_service`, `self.character_service`, etc.

### Acceder a DB
```python
from app.models.database import SessionLocal
session = SessionLocal()
# ... query ...
session.close()
```

### Añadir modelo ORM
1. Crear clase en `app/models/pss_models.py` heredando de `Base`
2. Incluir migraciones si es necesario
3. Usar en servicios vía `SessionLocal()` factories

## Gotchas & Troubleshooting

### Database locks
- SQLite con WAL mode: `PRAGMA journal_mode=WAL` ya activo
- Si `database is locked`: aumentar `busy_timeout` en `app/models/database.py`
- Tests: limpiar `.env` antes de correr si `DATABASE_URL` está seteada globalmente

### mitmproxy 11.0.2
- Pinned version por cambios semver. No actualizar sin validación.
- Requiere librerías del sistema en Linux (ver **Deps Linux CI** arriba).

### Imports desde `native_app/`
- Siempre usar imports relativos a `app.*` (no paths absolutos)
- Tests funcionan porque `pythonpath = ["."]` en `pyproject.toml`

## Database Models

Tabla principal:
- **BattleReplayNormalized**: evento principal de captura con battle_id, player_id, opponent_id, resultado
- **Ship**: naves en batalla (ship_id, room_id, battle_id)
- **Room**: salas de nave (room_id, level, equipment)
- **Character**: tripulación (character_id, room_id, ability)
- **Command**: comandos de batalla (tipo, params)

Ver `app/models/pss_models.py` para esquema ORM completo.

## Related Documentation
- [CONTRIBUTING.md](CONTRIBUTING.md) — Branch strategy & CI/CD
- [docs/CODEBASE_ONBOARDING.md](docs/CODEBASE_ONBOARDING.md) — Arquitectura detallada & flujo principal
- [docs/INSTALLATION.md](docs/INSTALLATION.md) — Setup de entorno
- [docs/WORKFLOW.md](docs/WORKFLOW.md) — Dev workflow recomendado
- [README.md](README.md) — Quick start & features

