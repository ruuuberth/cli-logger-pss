# Instalación (Estado Actual: Native App)

Este proyecto ahora se ejecuta como app nativa en Python (`native_app/`).

## Requisitos
- Python 3.11+
- pip
- Entorno virtual `venv` (recomendado y usado en esta guía)

## 1) Clonar y entrar al proyecto
```bash
git clone <repository-url>
cd "Logger PSS"
```

## 2) Instalar dependencias nativas
```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
```

`venv` en corto:
- `python3 -m venv .venv`: crea un Python aislado para este proyecto.
- `source .venv/bin/activate`: activa ese entorno en tu shell actual.
- `deactivate`: sale del entorno.
- En cada terminal nueva debes volver a activar el entorno.

Verificación rápida:
```bash
which python
which pip
```
Ambos deben resolver dentro de `native_app/.venv/`.

## 3) Ejecutar app en desarrollo (primera vez)
```bash
pss-native
# alternativa: python -m app.main
```

La app abrirá una ventana nativa (PySide6).

## 4) Ejecutar app en desarrollo (siguientes veces)
```bash
cd native_app
source .venv/bin/activate
pss-native
```

## 5) Compilar distribución
```bash
cd native_app
./scripts/build.sh
```

Salida esperada:
- Linux/macOS: `native_app/dist/pss-logger-native`
- Windows: `native_app/dist/pss-logger-native.exe`

## Funcionalidades actuales
- Detección automática de carpeta `SavySoda/Pixel Starships`
- Selección manual de carpeta (fallback)
- Escaneo de archivos exportables (`xml/json/txt/log/csv/ini/cfg/yaml`)
- Importación local a SQLite

## Base de datos en desarrollo
- Con `native_app/.env` de desarrollo, `DATABASE_URL=sqlite:///./pss_logger_dev.db`.
- Eso apunta a `native_app/pss_logger_dev.db`.
- Si `DATABASE_URL` no está definido, la app usa fallback: `~/.pss_logger/pss_logger.db`.

## Items: fuentes disponibles en la app
- `BaseDeDatos`: lee datos ya parseados en SQLite.
- `API`: consulta la API oficial y persiste resultados; su caché de memoria se controla con `ITEMS_API_CACHE_TTL_SECONDS` (default `86400`, 1 día).
- `ArchivosLocales`: parsea `ItemDesigns.txt` importado desde archivos del juego.
- El timeout de llamadas remotas usa `PSS_API_REQUEST_TIMEOUT_SECONDS` (segundos).

## VSCode: depuración y ejecución
Archivos de configuración incluidos:
- `.vscode/settings.json`
- `.vscode/launch.json`
- `.vscode/tasks.json`

Flujo:
1. Abrir el repo en VSCode.
2. Confirmar entorno activo en terminal: `cd native_app && source .venv/bin/activate`.
3. Ejecutar con depuración: `Run and Debug` -> `Native App (Debug)`.
4. Ejecutar sin depurar: `Terminal` -> `Run Task` -> `Run Native App`.

## Estructura vigente
```text
native_app/
  app/
    main.py
    core/
    models/
    services/
    ui/
  scripts/
  requirements.txt

docs/
  INSTALLATION.md
  CODEBASE_ONBOARDING.md
  WORKFLOW.md
  NATIVE_ROADMAP.md

archive/deprecated/
  frontend/
  backend/
  backend_legacy/
```

## Notas importantes
- La arquitectura web/Docker quedó archivada en `archive/deprecated/`.
- La rama base de trabajo es `main`.
- Flujo de ramas y PRs: ver `docs/WORKFLOW.md`.
