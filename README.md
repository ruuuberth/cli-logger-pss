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
- `API_FLOW_ENABLED`
- `MITMPROXY_BINARY`
- `MITMPROXY_LISTEN_HOST`
- `MITMPROXY_LISTEN_PORT`
- `API_FLOW_BODY_MAX_CHARS`
- `API_FLOW_RETENTION_DAYS`
- `API_FLOW_MAX_DB_MB`
- `API_FLOW_IGNORE_HOSTS`

### Base de datos en desarrollo

- Con `native_app/.env` de desarrollo (`DATABASE_URL=sqlite:///./pss_logger_dev.db`), la app usa:
  - `native_app/pss_logger_dev.db`
- Si no existe `DATABASE_URL`, la app usa fallback en:
  - `~/.pss_logger/pss_logger.db`

## Enfoque actual de la UI

- La app se opera desde la pestaña `Flujo de la API` para logging de batallas.
- Se removieron de navegación principal las opciones de:
  - Importación desde archivos locales.
  - Consulta directa de catálogos/items por API.

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

- Captura de tráfico API en tiempo real (pestaña `Flujo de la API`) usando `mitmproxy`
- Almacenamiento histórico en SQLite con retención por TTL/tamaño
- Filtros, paginación y panel de detalle JSON por evento

## Flujo de la API (mitmproxy)

1. Instalar dependencias:
```bash
cd native_app
source .venv/bin/activate
pip install -e .
```
2. Abrir la pestaña `Flujo de la API`.
3. Pulsar `Iniciar captura`.
4. Configurar el juego para usar proxy `127.0.0.1:8081`.
5. Si un host no permite MITM (pinning/TLS estricto), agrégalo a passthrough:
   - `API_FLOW_IGNORE_HOSTS=player-auth.services.api.unity.com`
   - varios hosts separados por coma.

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
      api_flow_capture.py
      api_flow_storage.py
      mitm_api_flow_addon.py
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
