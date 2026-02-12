# Onboarding técnico del código base

## 1) Visión general

Logger-PSS es una aplicación full stack para consultar datos de Pixel Starships, cachearlos en base de datos y visualizarlos en una interfaz web.

Arquitectura de alto nivel:

- **Frontend (React + MUI)**: interfaz de usuario con páginas para dashboard, ítems, naves y tripulación.
- **Backend (FastAPI)**: API REST que encapsula la lógica de consulta y caché.
- **Persistencia (SQLAlchemy + PostgreSQL/SQLite)**: guarda diseños ya consultados para reducir llamadas externas.
- **Orquestación (Docker Compose)**: ejecuta frontend, backend, base de datos y Redis en local.

## 2) Estructura por carpetas

- `frontend/`: cliente React, rutas y componentes visuales.
- `backend/`: servicio FastAPI, modelos y endpoints.
- `docs/`: guías de instalación y uso con Docker.
- `docker-compose.yml` / `docker-compose.dev.yml`: despliegue local en modo prod/dev.

## 3) Cómo fluye una petición (request lifecycle)

Ejemplo: cargar ítems en la página de Items.

1. `frontend/src/pages/Items.js` llama a `pssApi.getItems()` al montar el componente.
2. `frontend/src/services/api.js` hace `GET /api/v1/items/designs`.
3. `backend/app/api/v1/endpoints/items.py` recibe la request y crea `PSSService`.
4. `backend/app/services/pss_service.py`:
   - primero busca cache en DB (`ItemDesign`),
   - si no existe, consulta API externa (`pssapi`),
   - guarda el resultado en DB,
   - devuelve datos serializados.
5. El frontend renderiza la tabla y aplica búsqueda local por texto.

El mismo patrón aplica para naves y tripulaciones.

## 4) Componentes clave que debes entender

### Backend

- **Entrada de app**: `backend/app/main.py`
  - Configura FastAPI, CORS y monta el router v1.
- **Configuración**: `backend/app/core/config.py`
  - Define variables como `DATABASE_URL`, `API_V1_STR` y hosts permitidos.
- **Router de API**: `backend/app/api/v1/api.py`
  - Agrega rutas de `items`, `ships` y `crews`.
- **Endpoints**: `backend/app/api/v1/endpoints/*.py`
  - Son delgados: delegan casi todo al servicio.
- **Servicio de dominio**: `backend/app/services/pss_service.py`
  - Orquesta cache + llamada externa + serialización.
- **Modelos y DB**:
  - `backend/app/models/database.py`: engine, sesión y dependencia `get_db`.
  - `backend/app/models/pss_models.py`: tablas `ItemDesign`, `ShipDesign`, `CrewDesign`.

### Frontend

- **Bootstrap app**: `frontend/src/index.js`
  - Configura tema MUI y router.
- **Ruteo principal**: `frontend/src/App.js`
  - Mapea `/`, `/items`, `/ships`, `/crews`.
- **Cliente HTTP**: `frontend/src/services/api.js`
  - Centraliza `axios` y base URL.
- **Páginas**: `frontend/src/pages/*.js`
  - Dashboard para conteos; tablas filtrables para entidades.
- **Navegación**: `frontend/src/components/Navbar.js`

## 5) Decisiones técnicas importantes

- **Cache read-through en backend**: primero DB, luego API externa.
- **Endpoints simples y capa de servicio fuerte**: facilita mantenimiento.
- **Serialización manual**: controla formato de respuesta al frontend.
- **Frontend sin estado global complejo**: usa `useState/useEffect` local por página.
- **Configuración por entorno**: backend usa `.env`; frontend usa `REACT_APP_API_URL`.

## 6) Riesgos / deuda técnica a vigilar

- Manejo de errores genérico (`except Exception`) en endpoints puede ocultar errores de negocio.
- Llamadas asíncronas a API externa con persistencia síncrona en SQLAlchemy clásico.
- No hay capa de esquemas Pydantic para respuestas tipadas en endpoints.
- Búsqueda y paginación se hacen en cliente; puede escalar mal con datasets grandes.
- El import de `pssapi` es tolerante a fallo y retorna vacío, útil para desarrollo pero puede esconder errores de integración.

## 7) Qué aprender después (ruta recomendada para alguien nuevo)

1. **FastAPI fundamentals**
   - Dependency Injection (`Depends`), routers y manejo de errores HTTP.
2. **SQLAlchemy ORM**
   - Sesiones, modelos, ciclos de vida y migraciones (idealmente añadir Alembic).
3. **React hooks + MUI**
   - Patrones de carga de datos (`useEffect`) y composición de UI.
4. **Docker Compose del repo**
   - Entender diferencias entre archivos `docker-compose.yml` y `docker-compose.dev.yml`.
5. **Calidad y observabilidad**
   - Añadir tests (backend + frontend), logging estructurado y métricas básicas.

## 8) Primeras tareas de onboarding sugeridas

- Levantar entorno dev con `docker compose -f docker-compose.dev.yml up --build`.
- Recorrer `/docs` y probar endpoints en `/docs` de FastAPI.
- Agregar un endpoint pequeño nuevo (ej. estadísticas agregadas) para entender el flujo end-to-end.
- Implementar pruebas mínimas en backend para un endpoint de `items`.
