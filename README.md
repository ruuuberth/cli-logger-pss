# PixelStarships Logger - Native

Proyecto migrado a una app nativa multiplataforma centrada en Python.

## Estado actual

- App principal: `native_app/` (PySide6 + SQLite)
- Código backend reutilizable migrado a `native_app/app/core`, `native_app/app/models`, `native_app/app/services`
- Legacy archivado: `archive/deprecated/`

## Estrategia de ramas

- Rama base activa (nativa): `main`
- Ramas web en mantenimiento: `web/main`, `web/develop`
- Las nuevas features se integran por PR a `main`
- Reglas de colaboración: `CONTRIBUTING.md`

## Ejecutar app nativa en desarrollo

### Flujo recomendado (primera vez)

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
# alternativa: python -m app.main
```

### Flujo recomendado (siguientes veces)

```bash
cd native_app
source .venv/bin/activate
pss-native
```

### `venv` explicado rápido

- `python3 -m venv .venv`: crea un entorno Python local dentro de `native_app/.venv`.
- `source .venv/bin/activate`: activa ese entorno en tu terminal actual.
- Mientras esté activo, `python` y `pip` apuntan al entorno local del proyecto.
- Para salir del entorno: `deactivate`.
- Si abres una terminal nueva, debes volver a activar (`source .venv/bin/activate`).

Atajos para verificar:

```bash
which python
which pip
```

Deben apuntar a `.../native_app/.venv/...`.

## Compilar distribución

```bash
cd native_app
./scripts/build.sh
```

Salida esperada:
- Linux/macOS: `native_app/dist/pss-logger-native`
- Windows: `native_app/dist/pss-logger-native.exe`

## Variables de entorno

- Ejemplo base: `.env.example`
- Ejemplo desarrollo: `.env.dev.example`
- Recomendado para correr la app local:
  - `cd native_app && cp ../.env.dev.example .env`

Variables principales:
- `DATABASE_URL`
- `PSS_API_BASE_URL`
- `PSS_API_REQUEST_TIMEOUT_SECONDS`
- `PSS_CHECKSUM_KEY`
- `DESIGNS_CACHE_TTL_SECONDS`
- `ITEMS_API_CACHE_TTL_SECONDS`
- `BATTLE_REPORT_CACHE_TTL_SECONDS`

### Base de datos en desarrollo

- Con `native_app/.env` de desarrollo (`DATABASE_URL=sqlite:///./pss_logger_dev.db`), la app usa:
  - `native_app/pss_logger_dev.db`
- Si no existe `DATABASE_URL`, la app usa fallback en:
  - `~/.pss_logger/pss_logger.db`

## Items en GUI: fuentes de datos

- Pestaña: `Items`
- Fuente `BaseDeDatos`: usa `item_designs` en SQLite local (rápido, sin red).
- Fuente `API`: consulta la API oficial y actualiza SQLite; usa caché en memoria con TTL por `ITEMS_API_CACHE_TTL_SECONDS` (default 86400 = 1 día).
- Fuente `ArchivosLocales`: parsea `ItemDesigns.txt` importado desde la carpeta del juego.
- Nota: el checkbox de refresco forzado aplica a llamadas de API, no a DB/local.

## VSCode: ejecución y depuración

Archivos versionados:
- `.vscode/settings.json`
- `.vscode/launch.json`
- `.vscode/tasks.json`

Uso:
1. Abrir el workspace en la raíz del repo.
2. Activar entorno: `cd native_app && source .venv/bin/activate`.
3. En VSCode, usar `Run and Debug` con `Native App (Debug)`.
4. Para ejecutar sin depurar, usar task `Run Native App`.

## Funciones implementadas en la app nativa

- Detección automática de carpeta `SavySoda/Pixel Starships`
- Selección manual de carpeta (fallback)
- Escaneo de archivos exportables (`xml/json/txt/log/csv/ini/cfg/yaml`)
- Importación local a SQLite

## Estructura

```text
native_app/
  app/
    core/
      config.py
    main.py
    models/
      database.py
      pss_models.py
    services/
      game_data.py
      pss_service.py
      storage.py
    ui/
      main_window.py
  scripts/
    build.sh
  requirements.txt

archive/deprecated/
  frontend/
  backend/
    api/
    desktop_main.py
    main.py
    tests/
  backend_legacy/
  docker-compose.yml
  docker-compose.dev.yml
  Dockerfile
  Dockerfile.dev
  DOCKER.md
```
