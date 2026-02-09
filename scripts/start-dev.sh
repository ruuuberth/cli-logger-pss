#!/bin/bash

echo "🛠️  Iniciando PixelStarships Logger con Docker Compose (Desarrollo)..."

# Verificar Docker y Docker Compose
if ! command -v docker &> /dev/null; then
    echo "❌ Docker no encontrado. Por favor instala Docker."
    exit 1
fi

if ! command -v docker &> /dev/null; then
    echo "❌ Docker no encontrado. Por favor instala Docker."
    exit 1
fi

# Verificar Docker Compose (V2 o V1)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose no encontrado. Por favor instala Docker Compose."
    exit 1
fi

# Verificar archivo .env.dev
if [ ! -f ".env.dev" ]; then
    echo "📝 Creando archivo .env.dev desde .env.dev.example..."
    cp .env.dev.example .env.dev
    echo "⚠️  Por favor revisa y ajusta el archivo .env.dev según tus necesidades."
fi

# Detener contenedores existentes
echo "🛑 Deteniendo contenedores de desarrollo existentes..."
$DOCKER_COMPOSE_CMD -f docker-compose.dev.yml down

# Construir y iniciar contenedores de desarrollo
echo "🔨 Construyendo imágenes Docker de desarrollo..."
$DOCKER_COMPOSE_CMD -f docker-compose.dev.yml build

echo "🚀 Iniciando servicios de desarrollo..."
$DOCKER_COMPOSE_CMD -f docker-compose.dev.yml up -d

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios se inicien..."
sleep 15

# Verificar estado de los servicios
echo "📊 Verificando estado de los servicios..."
$DOCKER_COMPOSE_CMD -f docker-compose.dev.yml ps

# Mostrar logs
echo "📋 Mostrando logs recientes..."
$DOCKER_COMPOSE_CMD -f docker-compose.dev.yml logs --tail=20

echo ""
echo "✅ ¡PixelStarships Logger (Desarrollo) iniciado exitosamente!"
echo ""
echo "🌐 Servicios de desarrollo disponibles:"
echo "   Frontend: http://localhost:3001"
echo "   Backend API: http://localhost:8001"
echo "   API Docs: http://localhost:8001/docs"
echo "   Base de Datos: localhost:5433"
echo "   Redis: localhost:6379"
echo ""
echo "🔧 Comandos útiles:"
echo "   Ver logs: $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml logs -f [servicio]"
echo "   Detener: $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml down"
echo "   Reiniciar: $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml restart [servicio]"
echo "   Ejecutar comando: $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml exec [servicio] [comando]"
echo ""
echo "💡 Los cambios en el código se reflejarán automáticamente (hot reload)"