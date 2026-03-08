# Instalación

## Requisitos

- Python 3.11+
- pip

## Setup

```bash
git clone <repository-url>
cd "Logger PSS"
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
```

## Ejecutar

```bash
cd native_app
source .venv/bin/activate
pss-native
```

## Proxy del juego

Configura el cliente/juego con proxy local:
- host: `127.0.0.1`
- port: `8081` (o el que definas)

## Captura por defecto

- Se captura todo el flujo (excepto hosts en `API_FLOW_IGNORE_HOSTS`).
- La UI principal muestra solo batallas `GetBattle3` normalizadas.

Variables para ajustar filtros:
- `API_FLOW_CAPTURE_HOST_ALLOWLIST`
- `API_FLOW_CAPTURE_PATH_ALLOWLIST`
