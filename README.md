# Logger PSS

`Logger PSS` es una app de escritorio para analizar batallas de **Pixel Starships** a partir del tráfico de red del juego.

## Que hace

1. Captura respuestas de batalla (`GetBattle3`) usando `mitmproxy`.
2. Guarda el evento crudo y una versión limpia del payload.
3. Normaliza los datos en tablas relacionales (nave, salas, tripulación, comandos).
4. Muestra los resultados en una UI con búsqueda, paginación e inspectores.
5. Mantiene estadísticas H2H (head-to-head) por pareja de jugadores.

## Para que sirve

- Revisar rápidamente el resultado de combates capturados.
- Inspeccionar IA de salas y tripulación.
- Consultar tendencias entre dos jugadores (wins/losses H2H).
- Tener historial local para depuración y análisis.

## Inicio rapido

```bash
cd native_app
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cp ../.env.dev.example .env
pss-native
```

## Configuracion minima recomendada (opcional)

La app funciona sin `.env` usando defaults.  
Si quieres ajustar comportamiento avanzado, usa `native_app/.env`:

- `API_FLOW_ENABLED=true`
- `MITMPROXY_BINARY=mitmdump`
- `MITMPROXY_LISTEN_HOST=127.0.0.1`
- `MITMPROXY_LISTEN_PORT=8081`
- `API_FLOW_CAPTURE_HOST_ALLOWLIST=["api.pixelstarships.com"]`
- `API_FLOW_CAPTURE_PATH_ALLOWLIST=["/BattleService/GetBattle3"]`

Con esto la captura queda enfocada en batallas y evita ruido de otros servicios.

Formato recomendado para listas en `.env`: JSON array.
Ejemplo: `API_FLOW_IGNORE_HOSTS=["host1","host2"]`
Compatibilidad temporal: el formato CSV (`host1,host2`) sigue funcionando en esta release pero queda deprecado.

## Seguridad

- No se deben commitear archivos `.env` reales.
- Solo se permiten `.env.example` y `.env.dev.example`.

## Datos que guarda

Base SQLite local (`native_app/pss_logger_dev.db` o `native_app/pss_logger.db`):

- `api_flow_events`
- `battle_replays_normalized`
- `battle_replay_ships`
- `battle_replay_rooms`
- `battle_replay_characters`
- `battle_replay_commands`
- `player_matchup_logs`
- `player_matchup_stats`

## Flujo de uso

1. Abrir la app.
2. Iniciar captura (si no arranca automaticamente).
3. Jugar batallas.
4. Volver a la app y abrir `Inspector` en una fila.
5. Revisar detalle por naves, salas, tripulación y comandos.

## Build del binario nativo

```bash
cd native_app
./scripts/build.sh
```

Salida principal:
- `native_app/dist/pss-logger-native-linux-portable.zip` (Linux)
- `native_app/dist/pss-logger-native-windows-portable.zip` (Windows, desde runner Windows)

## Publicación automática de binarios

- PR a `develop` o `main`: compila Linux + Windows y sube ZIP portable de CI.
- Push a `develop`: actualiza pre-release `develop-latest` con ZIPs + `SHA256SUMS.txt`.
- Push de tag `v*`: crea release estable con ZIPs Linux/Windows + `SHA256SUMS.txt`.
- Política de assets: no se publican binarios sueltos (`pss-logger-native` / `.exe`), solo ZIP portable.

Si configuras `SIGNING_PRIVATE_KEY` (y opcionalmente `SIGNING_PASSPHRASE`), también se publica `SHA256SUMS.txt.asc`.

Los ZIPs incluyen runtime de mitmproxy y `THIRD_PARTY_NOTICES.txt`.

## Flujo de ramas

- `develop`: rama de desarrollo e integración.
- `main`: rama de producción estable.
- Features/fixes normales: PR hacia `develop`.
- Publicación estable: merge controlado a `main` y tag `v*`.

## Documentacion relacionada

- `native_app/README.md` (detalle tecnico del modulo nativo)
- `docs/CODEBASE_ONBOARDING.md`
- `docs/TEMP_GOVERNANCE_PROTOCOL.md` (protocolo temporal sin branch protection)
- `CONTRIBUTING.md`
