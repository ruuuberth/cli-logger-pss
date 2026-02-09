# Guía de Instalación y Uso

## 🐳 Método Recomendado: Docker Compose

### Requisitos Previos
- Docker 20.10 o superior
- Docker Compose 2.0 o superior
- Git

### Instalación Rápida con Docker

#### 1. Clonar el Repositorio
```bash
git clone <repository-url>
cd "Logger PSS"
```

#### 2. Configurar Variables de Entorno
```bash
# Producción
cp .env.example .env

# Desarrollo (opcional)
cp .env.dev.example .env.dev
```

#### 3. Iniciar con Scripts Automatizados

**Producción:**
```bash
./scripts/start-prod.sh
```

**Desarrollo:**
```bash
./scripts/start-dev.sh
```

#### 4. Acceder a los Servicios

**Producción:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

**Desarrollo:**
- Frontend: http://localhost:3001
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

## 🔧 Método Manual: Sin Docker

### Requisitos Previos
- Python 3.11 o superior
- Node.js 16 o superior
- PostgreSQL 13 o superior (opcional, usa SQLite por defecto)
- Git

### Instalación Manual

#### 1. Clonar el Repositorio
```bash
git clone <repository-url>
cd "Logger PSS"
```

#### 2. Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env según tus necesidades
```

#### 3. Frontend
```bash
cd frontend
npm install

# Configurar variables de entorno
cp .env.example .env
# Editar .env según tus necesidades
```

#### 4. Base de Datos (Opcional)
```bash
# Usar SQLite (por defecto)
# No requiere configuración adicional

# O usar PostgreSQL
# Editar .env con tu configuración de PostgreSQL
```

## 🚀 Iniciar la Aplicación

### Método Docker (Recomendado)

#### Producción
```bash
./scripts/start-prod.sh
```

#### Desarrollo
```bash
./scripts/start-dev.sh
```

#### Comandos Docker Manuales
```bash
# Iniciar producción
docker-compose up -d

# Iniciar desarrollo
docker-compose -f docker-compose.dev.yml up -d

# Ver logs
docker-compose logs -f

# Detener
docker-compose down
```

### Método Manual

#### Backend (Terminal 1)
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```
El backend estará disponible en: http://localhost:8000

#### Frontend Web (Terminal 2)
```bash
cd frontend
npm start
```
El frontend web estará disponible en: http://localhost:3000

#### Frontend Desktop (Electron)
```bash
cd frontend
npm run electron-dev
```

## Características

### Backend
- **FastAPI**: Framework moderno y rápido
- **Base de Datos**: SQLite por defecto (configurable a PostgreSQL)
- **Caché**: Guarda respuestas de la API de PixelStarships
- **Endpoints REST**: Para items, naves y tripulación

### Frontend
- **React**: Biblioteca moderna de UI
- **Material-UI**: Componentes elegantes
- **Multiplataforma**: Web y Desktop (Electron)
- **Tiempo Real**: Actualización automática de datos

## API Endpoints

### Items
- `GET /api/v1/items/designs` - Listar todos los items
- `GET /api/v1/items/designs/{id}` - Obtener item específico

### Ships
- `GET /api/v1/ships/designs` - Listar todas las naves
- `GET /api/v1/ships/designs/{id}` - Obtener nave específica

### Crews
- `GET /api/v1/crews/designs` - Listar toda la tripulación
- `GET /api/v1/crews/designs/{id}` - Obtener tripulante específico

## Documentación de la API

Una vez iniciado el backend, visita:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Estructura del Proyecto

```
Logger PSS/
├── backend/                 # Backend Python
│   ├── app/
│   │   ├── api/            # Endpoints de la API
│   │   ├── core/           # Configuración
│   │   ├── models/         # Modelos de BD
│   │   └── services/       # Lógica de negocio
│   ├── requirements.txt
│   └── .env
├── frontend/               # Frontend React
│   ├── src/
│   │   ├── components/     # Componentes React
│   │   ├── pages/          # Páginas principales
│   │   └── services/       # Servicios API
│   ├── public/
│   └── package.json
└── docs/                   # Documentación
```

## Configuración

### Backend (.env)
```env
DATABASE_URL=sqlite:///./pss_logger.db
ALLOWED_HOSTS=http://localhost:3000
PSS_API_BASE_URL=https://api.pixelstarships.com
```

### Frontend (.env)
```env
REACT_APP_API_URL=http://localhost:8000
```

## Troubleshooting

### Problemas Comunes

1. **Error de conexión a la API**
   - Verifica que el backend esté corriendo
   - Revisa las URLs en los archivos .env

2. **Error de dependencias**
   - Actualiza pip: `pip install --upgrade pip`
   - Limpia caché de npm: `npm cache clean --force`

3. **Error de base de datos**
   - Elimina el archivo .db y reinicia el backend
   - Verifica los permisos del directorio

## Contribuir

1. Fork del proyecto
2. Crear rama de características
3. Hacer commit de cambios
4. Push a la rama
5. Crear Pull Request

## Licencia

MIT License - Ver archivo LICENSE para detalles