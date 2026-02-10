# PixelStarships Logger PSS

Proyecto en Python para conectar a la API de PixelStarships, guardar las respuestas y visualizarlas a través de un frontend multiplataforma.

## 🐳 Docker Compose - Recomendado

Este proyecto está optimizado para usar Docker Compose, que proporciona un entorno completo y aislado.

### 📋 Requisitos Previos
- Docker 20.10+ 
- Docker Compose V2 (docker compose)
- Git

### 🚀 Pasos para Ejecutar el Proyecto

#### 1) Clonar y Navegar al Proyecto
```bash
git clone <repository-url>
cd "Logger PSS"
```

#### 2) Configurar Variables de Entorno
```bash
# Producción
cp .env.example .env

# Desarrollo (opcional)
cp .env.dev.example .env.dev
```

#### 3) Iniciar el Proyecto

Opción A: Producción (Recomendada)
```bash
# Construir e iniciar servicios
docker compose up -d --build

# Verificar estado
docker compose ps

# Ver logs
docker compose logs -f
```

Opción B: Desarrollo (con Hot Reload)
```bash
# Construir e iniciar servicios de desarrollo
docker compose -f docker-compose.dev.yml up -d --build

# Verificar estado
docker compose -f docker-compose.dev.yml ps

# Ver logs
docker compose -f docker-compose.dev.yml logs -f
```

#### 4) Acceder a la Aplicación

Producción:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs

Desarrollo:
- Frontend: http://localhost:3001
- Backend API: http://localhost:8001
- API Docs: http://localhost:8001/docs

#### 5) Detener el Proyecto
```bash
# Producción
docker compose down

# Desarrollo
docker compose -f docker-compose.dev.yml down
```

### 🔧 Comandos Útiles

```bash
# Reconstruir imágenes
docker compose build --no-cache

# Reiniciar un servicio
docker compose restart backend

# Ver logs de un servicio
docker compose logs -f backend

# Acceder a un contenedor
docker compose exec backend bash

# Limpiar todo (contenedores, imágenes, volúmenes)
docker compose down -v --rmi all
docker system prune -f
```

## 📁 Estructura del Proyecto

```
Logger PSS/
├── backend/                 # Backend Python con FastAPI
│   ├── app/                # Aplicación principal
│   ├── models/             # Modelos de base de datos
│   ├── services/           # Servicios de API
│   ├── Dockerfile          # Imagen Docker de producción
│   └── Dockerfile.dev      # Imagen Docker de desarrollo
├── frontend/               # Frontend React
│   ├── src/                # Código fuente
│   ├── public/             # Archivos públicos
│   ├── Dockerfile          # Imagen Docker de producción
│   └── Dockerfile.dev      # Imagen Docker de desarrollo
├── scripts/                # Scripts de automatización
├── docker-compose.yml      # Configuración Docker (producción)
├── docker-compose.dev.yml  # Configuración Docker (desarrollo)
└── docs/                   # Documentación
```

## 🚀 Características

- **Backend**: FastAPI con conexión a API de PixelStarships
- **Base de Datos**: PostgreSQL con caché de respuestas
- **Frontend**: React con Material-UI
- **Multiplataforma**: Web y Desktop (Electron)
- **Docker**: Contenedores listos para producción y desarrollo
- **API Wrapper**: Usando pssapi.py oficial
- **Redis**: Caché adicional para mejorar rendimiento

## 🐋 Servicios Docker

### Producción (docker-compose.yml)
- **Frontend**: Nginx + React (puerto 3000)
- **Backend**: FastAPI (puerto 8000)
- **Base de Datos**: PostgreSQL (puerto 5432)
- **Redis**: Caché (puerto 6379)

### Desarrollo (docker-compose.dev.yml)
- **Frontend**: React Dev Server (puerto 3001)
- **Backend**: FastAPI con hot reload (puerto 8001)
- **Base de Datos**: PostgreSQL (puerto 5433)
- **Redis**: Caché (puerto 6379)

## ⚙️ Configuración

### Variables de Entorno
Copia los archivos de ejemplo y ajústalos:
```bash
cp .env.example .env          # Producción
cp .env.dev.example .env.dev  # Desarrollo
```

### Archivos de Configuración Principales
- `.env` - Variables de entorno de producción
- `.env.dev` - Variables de entorno de desarrollo
- `docker-compose.yml` - Servicios de producción
- `docker-compose.dev.yml` - Servicios de desarrollo

## 🔧 Comandos Docker

### Iniciar Servicios
```bash
# Producción
docker-compose up -d

# Desarrollo
docker-compose -f docker-compose.dev.yml up -d
```

### Ver Logs
```bash
# Todos los servicios
docker-compose logs -f

# Servicio específico
docker-compose logs -f backend
```

### Detener Servicios
```bash
# Producción
docker-compose down

# Desarrollo
docker-compose -f docker-compose.dev.yml down
```

### Reconstruir Imágenes
```bash
docker-compose build --no-cache
```

## 🌐 Acceso a los Servicios

### Producción
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Base de Datos**: localhost:5432

### Desarrollo
- **Frontend**: http://localhost:3001
- **Backend API**: http://localhost:8001
- **API Docs**: http://localhost:8001/docs
- **Base de Datos**: localhost:5433

## 📦 Instalación Manual (Sin Docker)

Si prefieres no usar Docker, puedes instalar manualmente:

### Backend
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm start
```

## 🔍 Troubleshooting Docker

### Problemas Comunes

1. **Puertos en uso**
   ```bash
   # Verificar puertos
   netstat -tulpn | grep :3000
   
   # Cambiar puertos en docker-compose.yml
   ```

2. **Permisos de Docker**
   ```bash
   sudo usermod -aG docker $USER
   # Reiniciar sesión
   ```

3. **Limpiar caché de Docker**
   ```bash
   docker system prune -a
   ```

4. **Reconstruir todo**
   ```bash
   ./scripts/cleanup.sh all
   ./scripts/start-prod.sh
   ```

## 📚 Documentación Adicional

- [Guía de Instalación Detallada](docs/INSTALLATION.md)
- [Documentación de la API](http://localhost:8000/docs)
- [Guía de Desarrollo](docs/DEVELOPMENT.md)
