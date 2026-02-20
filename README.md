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

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
# alternativa: python -m app.main
```

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
- `PSS_CHECKSUM_KEY`
- `DESIGNS_CACHE_TTL_SECONDS`
- `BATTLE_REPORT_CACHE_TTL_SECONDS`

## Funciones implementadas en la app nativa

- Detección automática de carpeta `SavySoda/Pixel Starships`
- Selección manual de carpeta (fallback)
- Escaneo de archivos exportables (`xml/json/txt/log/csv/ini/cfg/yaml`)
- Importación local a SQLite (`~/.pss_logger/pss_logger.db`)

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
