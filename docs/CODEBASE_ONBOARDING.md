# Onboarding Técnico (Native App)

## 1) Visión general

`Logger PSS` es ahora una app nativa de escritorio, multiplataforma, centrada en Python.

Arquitectura vigente:
- **UI nativa**: PySide6 (`native_app/app/ui/main_window.py`)
- **Lógica de negocio**: servicios Python (`native_app/app/services/`)
- **Persistencia local**: SQLite
- **Modelos/config**: `native_app/app/models/` y `native_app/app/core/`

Legacy web/backend se conserva en `archive/deprecated/` solo como referencia.

## 2) Estructura clave

- `native_app/app/main.py`: entrypoint de la app.
- `native_app/app/ui/main_window.py`: ventana principal y acciones del usuario.
- `native_app/app/services/game_data.py`: detección/escaneo de carpeta del juego.
- `native_app/app/services/storage.py`: importación y guardado en SQLite.
- `native_app/app/services/pss_service.py`: lógica de dominio migrada.
- `native_app/app/models/*.py`: modelos y acceso de datos.
- `native_app/app/core/config.py`: configuración central.

## 3) Flujo funcional principal

1. Usuario abre app nativa.
2. Detecta automáticamente carpeta `SavySoda/Pixel Starships` o la selecciona manualmente.
3. App escanea archivos exportables.
4. App importa contenido a SQLite local.
5. Datos quedan disponibles para siguientes vistas/consultas.

## 4) Decisiones técnicas actuales

- Se prioriza app nativa única (sin separación frontend/backend HTTP).
- Se mantiene compatibilidad con lógica previa migrando módulos de dominio.
- Se preserva historial técnico en `archive/deprecated/` para trazabilidad.

## 5) Riesgos/deuda actual

- Persistencia duplicada a consolidar (`sqlite3` directo + modelos SQLAlchemy).
- `pss_service.py` aún requiere integración completa a UI.
- Falta pipeline CI/CD multi-OS para releases automáticos.

## 6) Siguiente ruta recomendada

1. Unificar capa de persistencia.
2. Conectar pantallas nativas a `pss_service` (items/ships/crews/battles).
3. Añadir tests de servicios críticos.
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
