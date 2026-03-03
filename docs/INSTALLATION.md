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

## Funcionalidad actual
- Captura de tráfico de juego en tiempo real desde `Flujo de la API` (battle logger).
- Persistencia de requests/responses en SQLite local.
- Filtros, paginación y detalle JSON en la UI.

## Base de datos en desarrollo
- Con `native_app/.env` de desarrollo, `DATABASE_URL=sqlite:///./pss_logger_dev.db`.
- Eso apunta a `native_app/pss_logger_dev.db`.
- Si `DATABASE_URL` no está definido, la app usa fallback: `~/.pss_logger/pss_logger.db`.

## Flujo de la API (mitmproxy)

- Pestaña nativa: `Flujo de la API`.
- La app inicia `mitmdump` para capturar llamadas en tiempo real.
- Configura el cliente/juego para usar proxy local `127.0.0.1:8081` (o el host/puerto definidos en `.env`).

Variables:
- `API_FLOW_ENABLED`
- `MITMPROXY_BINARY`
- `MITMPROXY_LISTEN_HOST`
- `MITMPROXY_LISTEN_PORT`
- `API_FLOW_BODY_MAX_CHARS`
- `API_FLOW_RETENTION_DAYS`
- `API_FLOW_MAX_DB_MB`
- `API_FLOW_IGNORE_HOSTS` (lista separada por coma para passthrough)

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
