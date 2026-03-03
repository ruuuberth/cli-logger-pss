# Onboarding Técnico (Native App)

## 1) Visión general

`Logger PSS` es ahora una app nativa de escritorio, multiplataforma, centrada en Python.

Arquitectura vigente:
- **UI nativa**: PySide6 (battle logger) (`native_app/app/ui/main_window.py`)
- **Captura de tráfico**: `mitmdump` + addon (`native_app/app/services/mitm_api_flow_addon.py`)
- **Persistencia local**: SQLite (`api_flow_events`)
- **Modelos/config**: `native_app/app/models/` y `native_app/app/core/`

Legacy web/backend se conserva en `archive/deprecated/` solo como referencia.

## 2) Estructura clave

- `native_app/app/main.py`: entrypoint de la app.
- `native_app/app/ui/main_window.py`: ventana principal y acciones del usuario.
- `native_app/app/services/api_flow_capture.py`: lifecycle de `mitmdump` (start/stop/estado).
- `native_app/app/services/mitm_api_flow_addon.py`: normaliza eventos de request/response.
- `native_app/app/services/api_flow_storage.py`: persistencia, consulta y retención de eventos.
- `native_app/app/models/*.py`: modelos y acceso de datos.
- `native_app/app/core/config.py`: configuración central.

## 3) Flujo funcional principal

1. Usuario abre app nativa.
2. Inicia captura en `Flujo de la API`.
3. Juego envía tráfico vía proxy local (`mitmproxy`).
4. App persiste requests/responses en SQLite.
5. Usuario explora historial con filtros, paginación y detalle.

## 4) Decisiones técnicas actuales

- Se prioriza app nativa única (sin separación frontend/backend HTTP).
- Se mantiene compatibilidad con lógica previa migrando módulos de dominio.
- Se preserva historial técnico en `archive/deprecated/` para trazabilidad.

## 5) Riesgos/deuda actual

- Cobertura de tests todavía enfocada en servicios base.
- Algunos hosts Unity usan TLS estricto y requieren passthrough.
- Falta pipeline CI/CD multi-OS para releases automáticos.

## 6) Siguiente ruta recomendada

1. Mejorar detección/diagnóstico de hosts con TLS estricto.
2. Añadir tests de captura y retención.
3. Extender vistas para análisis específico de batallas.
4. Madurar build de distribución para Windows/Linux/macOS.

## 7) Comandos útiles

```bash
# Ejecutar app
cd native_app
pss-native
# alternativa: python -m app.main

# Build local
cd native_app
./scripts/build.sh

# Crear rama desde main
./scripts/new-branch.sh feat mi-cambio
```
