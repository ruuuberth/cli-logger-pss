# AGENTS.md — GUI-Logger-PSS

## Proyecto
App CLI (español) para capturar e inspeccionar replays de batalla de **Pixel Starships** vía mitmproxy.  
Todo el código activo está en `native_app/`. La capa UI (`app/ui/`) es legacy — no tiene PySide.

## Comandos (ejecutar desde `native_app/`)
- **Ejecutar:** `python run.py`
- **Test (todo):** `python -m pytest`
- **Test (archivo):** `python -m pytest tests/test_<name>.py`
- **Test (caso):** `python -m pytest tests/test_<name>.py::test_<specific>`
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
- **Entrypoint:** `app/main.py:main()` → `configure_environment()` → `initialize_database()` → CLI interactiva via `CliManager`
- **Sin DI:** los servicios se instancian directamente en `CliManager.__init__()`
- **DB:** SQLite, default `~/.pss_logger/pss_logger.db` (directorio se auto-crea)
- **mitmproxy:** pinned `11.0.2` (breaking semver)

## Testing
- pytest config en `pyproject.toml`: `pythonpath = ["."]` — imports `app.xxx` funcionan desde `native_app/`
- No hay `conftest.py` ni `pytest.ini`
- `test_main_startup_smoke.py` está **skip completo** (tests GUI legacy)
- Sin dependencias externas; tests usan monkeypatch + stubs manuales (sin librería mock)
- Algunos tests crean `.env` temporales — asegurar que `DATABASE_URL` no esté seteada al correrlos

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
