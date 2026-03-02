# Native Migration Roadmap

## Objetivo
Consolidar `native_app/` como única aplicación activa y cerrar la etapa legacy web/backend.

## Estado actual
- Núcleo nativo operativo: `native_app/app/main.py`
- UI battle logger: `native_app/app/ui/main_window.py` (`Flujo de la API`)
- Captura runtime: `native_app/app/services/api_flow_capture.py`
- Persistencia de flujo: `native_app/app/services/api_flow_storage.py`
- Legacy archivado en `archive/deprecated/`

## Fase 1: Núcleo de datos
1. Definir una sola capa de persistencia (`sqlite3` o SQLAlchemy).
2. Ajustar modelos activos para uso nativo.
3. Centralizar paths/config en `native_app/app/core/config.py`.

## Fase 2: Integración de funcionalidades
1. Consolidar captura estable de tráfico de juego por proxy.
2. Afinar passthrough por host para dominios con TLS estricto.
3. Mejorar manejo de errores de red/handshake con mensajes accionables.

## Fase 3: UX nativa
1. Navegación por secciones (tabs/sidebar).
2. Tabla de flujo con filtros, búsqueda y paginación.
3. Vistas de historial de batallas y detalle de eventos.

## Fase 4: Calidad
1. Tests de captura, persistencia y retención.
2. Smoke tests de arranque + DB.
3. Validaciones de integridad de eventos capturados.

## Fase 5: Distribución
1. Estándar de build con `native_app/scripts/build.sh`.
2. Empaquetado por OS (Windows/Linux/macOS).
3. Versionado y publicación de artefactos.

## Fase 6: Cierre legacy
1. Mantener `archive/deprecated/` como referencia histórica.
2. Eliminar referencias legacy restantes en docs/scripts.
3. Tag de release base: `native-v1`.
