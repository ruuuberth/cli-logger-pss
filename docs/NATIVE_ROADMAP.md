# Native Migration Roadmap

## Objetivo
Consolidar `native_app/` como única aplicación activa, eliminando dependencias de arquitectura web/backend HTTP.

## Estado Actual
- UI nativa base en `native_app/app/ui/main_window.py`
- Servicios de importación local en `native_app/app/services/game_data.py` y `native_app/app/services/storage.py`
- Código legacy movido a `archive/deprecated/`
- Servicios de dominio migrados: `native_app/app/services/pss_service.py`

## Fase 1: Estabilización del núcleo nativo
1. Unificar persistencia:
   - decidir si `sqlite3` directo o SQLAlchemy como única capa.
2. Limpiar modelos:
   - separar tablas activas de tablas legacy no usadas.
3. Centralizar configuración:
   - rutas de DB, logs, cache y entorno desktop en `native_app/app/core/config.py`.

## Fase 2: Integración funcional completa
1. Conectar UI a `pss_service`:
   - items, ships, crews, batallas desde la app nativa.
2. Reemplazar flujos incompletos:
   - importación local y consultas API oficial en una misma interfaz.
3. Manejo de errores y estados:
   - timeouts, errores de red, reintentos, feedback al usuario.

## Fase 3: UX nativa moderna
1. Mejorar estructura visual:
   - navegación por secciones, layout responsive desktop.
2. Tabla y filtros:
   - búsqueda, ordenamiento, paginación local.
3. Historial y sincronización:
   - vista de imports previos y última actualización de datos.

## Fase 4: Distribución de producción
1. Pipeline de build:
   - PyInstaller/Nuitka por plataforma.
2. Artefactos:
   - Windows (`.exe`), Linux (AppImage/binario), macOS (`.app`).
3. Post-build:
   - smoke test automático de arranque y DB.

## Fase 5: Cierre de legacy
1. Congelar `archive/deprecated` como solo lectura.
2. Eliminar referencias legacy en docs/scripts.
3. Etiquetar release `native-v1`.

## Próximas 3 tareas recomendadas
1. Definir capa de persistencia única (`sqlite3` vs SQLAlchemy).
2. Conectar `pss_service` a una pantalla nativa de consulta (Items/Ships/Crews).
3. Agregar script de build multi-OS reproducible.
