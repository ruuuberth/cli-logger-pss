# Guía de Docker Compose

## 🐳 Descripción General

Este proyecto utiliza Docker Compose para orquestar todos los servicios necesarios para PixelStarships Logger. Docker Compose permite definir y ejecutar múltiples contenedores Docker como una aplicación unificada.

## 📋 Servicios Incluidos

### 1. Frontend (React + Nginx)
- **Producción**: Nginx sirviendo React build optimizado
- **Desarrollo**: React Dev Server con hot reload
- **Puertos**: 3000 (prod), 3001 (dev)

### 2. Backend (FastAPI)
- **Producción**: FastAPI optimizado
- **Desarrollo**: FastAPI con recarga automática
- **Puertos**: 8000 (prod), 8001 (dev)

### 3. Base de Datos (PostgreSQL)
- **Motor**: PostgreSQL 15 Alpine
- **Persistencia**: Volúmenes Docker
- **Puertos**: 5432 (prod), 5433 (dev)

### 4. Redis (Caché)
- **Motor**: Redis 7 Alpine
- **Persistencia**: Volúmenes Docker
- **Puerto**: 6379

## 🗂️ Archivos de Configuración

### docker-compose.yml (Producción)
```yaml
version: '3.8'
services:
  frontend:
    build: ./frontend
    ports: ["3000:80"]
  
  backend:
    build: ./backend
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql://...
  
  db:
    image: postgres:15-alpine
    ports: ["5432:5432"]
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### docker-compose.dev.yml (Desarrollo)
```yaml
version: '3.8'
services:
  frontend:
    build: 
      context: ./frontend
      dockerfile: Dockerfile.dev
    ports: ["3001:3000"]
    volumes: ["./frontend:/app"]
  
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile.dev
    ports: ["8001:8000"]
    volumes: ["./backend:/app"]
```

## 🚀 Scripts de Automatización

### start-prod.sh
Inicia el entorno de producción:
```bash
./scripts/start-prod.sh
```

**Acciones:**
1. Verifica Docker y Docker Compose
2. Crea .env si no existe
3. Detiene contenedores existentes
4. Construye imágenes
5. Inicia servicios
6. Muestra estado y logs

### start-dev.sh
Inicia el entorno de desarrollo:
```bash
./scripts/start-dev.sh
```

**Acciones:**
1. Verifica Docker y Docker Compose
2. Crea .env.dev si no existe
3. Usa docker-compose.dev.yml
4. Habilita volúmenes para hot reload
5. Inicia servicios en puertos diferentes

### cleanup.sh
Limpia contenedores e imágenes:
```bash
./scripts/cleanup.sh [all|prod|dev|containers|images|volumes]
```

**Opciones:**
- `all`: Elimina todo (contenedores, imágenes, volúmenes)
- `prod`: Limpia solo producción
- `dev`: Limpia solo desarrollo
- `containers`: Elimina solo contenedores
- `images`: Elimina solo imágenes
- `volumes`: Elimina solo volúmenes

## 🔧 Variables de Entorno

### .env (Producción)
```env
# Base de Datos
POSTGRES_DB=pixelstarships
POSTGRES_USER=pss_user
POSTGRES_PASSWORD=pss_password

# Backend
DATABASE_URL=postgresql://pss_user:pss_password@db:5432/pixelstarships
ALLOWED_HOSTS=http://localhost:3000,http://frontend

# Frontend
REACT_APP_API_URL=http://localhost:8000
```

### .env.dev (Desarrollo)
```env
# Base de Datos
POSTGRES_DB=pixelstarships_dev
POSTGRES_USER=pss_user
POSTGRES_PASSWORD=pss_password

# Backend
DATABASE_URL=postgresql://pss_user:pss_password@db:5432/pixelstarships_dev
ALLOWED_HOSTS=http://localhost:3001,http://frontend

# Frontend
REACT_APP_API_URL=http://localhost:8001
```

## 🐳 Dockerfiles

### Backend/Dockerfile (Producción)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Backend/Dockerfile.dev (Desarrollo)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

### Frontend/Dockerfile (Producción)
```dockerfile
# Build stage
FROM node:18-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY . .
RUN npm run build

# Production stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/nginx.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### Frontend/Dockerfile.dev (Desarrollo)
```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
```

## 🔄 Flujo de Trabajo

### Desarrollo
1. Usa `docker-compose.dev.yml`
2. Volúmenes montados para hot reload
3. Puertos diferentes para evitar conflictos
4. Logs detallados y modo debug

### Producción
1. Usa `docker-compose.yml`
2. Imágenes optimizadas y multi-stage
3. Sin volúmenes de código (solo datos)
4. Nginx como reverse proxy

### Despliegue
1. Construir imágenes: `docker-compose build`
2. Subir a registry: `docker push`
3. Descargar en servidor: `docker pull`
4. Iniciar con: `docker-compose up -d`

## 📊 Monitoreo y Logs

### Ver Logs
```bash
# Todos los servicios
docker-compose logs -f

# Servicio específico
docker-compose logs -f backend

# Últimas 50 líneas
docker-compose logs --tail=50
```

### Monitorear Recursos
```bash
# Uso de recursos
docker stats

# Inspeccionar contenedor
docker inspect pss_backend
```

### Acceder a Contenedores
```bash
# Bash en backend
docker-compose exec backend bash

# PSQL en base de datos
docker-compose exec db psql -U pss_user -d pixelstarships

# Redis CLI
docker-compose exec redis redis-cli
```

## 🛠️ Mantenimiento

### Actualizar Imágenes
```bash
# Descargar nuevas versiones
docker-compose pull

# Reconstruir con cambios locales
docker-compose build --no-cache
```

### Backup de Base de Datos
```bash
# Exportar datos
docker-compose exec db pg_dump -U pss_user pixelstarships > backup.sql

# Importar datos
docker-compose exec -T db psql -U pss_user pixelstarships < backup.sql
```

### Limpieza Periódica
```bash
# Limpiar contenedores detenidos
docker container prune

# Limpiar imágenes no usadas
docker image prune

# Limpiar volúmenes no usados
docker volume prune
```

## 🔒 Seguridad

### Buenas Prácticas
1. **No exponer puertos de base de datos** en producción
2. **Usar secrets** para contraseñas sensibles
3. **Limitar recursos** de los contenedores
4. **Actualizar imágenes** regularmente
5. **Usar redes privadas** entre servicios

### Configuración Segura
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '0.5'
    networks:
      - internal
    ports:
      - "127.0.0.1:8000:8000"  # Solo localhost
```

## 🚨 Troubleshooting

### Problemas Comunes

1. **Contenedor no inicia**
   ```bash
   docker-compose logs backend
   # Verificar errores de configuración
   ```

2. **Conexión a base de datos falla**
   ```bash
   # Verificar que la DB esté iniciada
   docker-compose ps db
   
   # Probar conexión
   docker-compose exec backend python -c "from app.models.database import engine; print(engine.execute('SELECT 1').scalar())"
   ```

3. **Frontend no se actualiza**
   ```bash
   # Reconstruir imagen
   docker-compose build --no-cache frontend
   
   # Verificar volúmenes en desarrollo
   docker-compose -f docker-compose.dev.yml config
   ```

4. **Permisos de archivos**
   ```bash
   # Fix permisos en Linux
   sudo chown -R $USER:$USER .
   chmod +x scripts/*.sh
   ```

### Comandos de Diagnóstico
```bash
# Estado completo
docker-compose ps

# Configuración generada
docker-compose config

# Eventos de Docker
docker events

# Inspeccionar red
docker network ls
docker network inspect logger_pss_pss_network
```