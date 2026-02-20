# Instalación (Estado Actual: Native App)

Este proyecto ahora se ejecuta como app nativa en Python (`native_app/`).

## Requisitos
- Python 3.11+
- pip
- (Opcional) entorno virtual `venv`

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
```

## 3) Ejecutar app en desarrollo
```bash
pss-native
# alternativa: python -m app.main
```

La app abrirá una ventana nativa (PySide6).

## 4) Compilar distribución
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
- Importación local a SQLite (`~/.pss_logger/pss_logger.db`)

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
