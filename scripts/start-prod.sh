#!/bin/bash

echo "🐳 Iniciando PixelStarships Logger con Docker Compose (Producción)..."

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

# Verificar archivo .env
if [ ! -f ".env" ]; then
    echo "📝 Creando archivo .env desde .env.example..."
    cp .env.example .env
    echo "⚠️  Por favor revisa y ajusta el archivo .env según tus necesidades."
fi

# Detener contenedores existentes
echo "🛑 Deteniendo contenedores existentes..."
$DOCKER_COMPOSE_CMD down

# Construir y iniciar contenedores
echo "🔨 Construyendo imágenes Docker..."
$DOCKER_COMPOSE_CMD build

echo "🚀 Iniciando servicios..."
$DOCKER_COMPOSE_CMD up -d

# Esperar a que los servicios estén listos
echo "⏳ Esperando a que los servicios se inicien..."
sleep 10

# Verificar estado de los servicios
echo "📊 Verificando estado de los servicios..."
$DOCKER_COMPOSE_CMD ps

# Mostrar logs
echo "📋 Mostrando logs recientes..."
$DOCKER_COMPOSE_CMD logs --tail=20

echo ""
echo "✅ ¡PixelStarships Logger iniciado exitosamente!"
echo ""
echo "🌐 Servicios disponibles:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo "   Base de Datos: localhost:5432"
echo "   Redis: localhost:6379"
echo ""
echo "🔧 Comandos útiles:"
echo "   Ver logs: $DOCKER_COMPOSE_CMD logs -f [servicio]"
echo "   Detener: $DOCKER_COMPOSE_CMD down"
echo "   Reiniciar: $DOCKER_COMPOSE_CMD restart [servicio]"
echo "   Ejecutar comando: $DOCKER_COMPOSE_CMD exec [servicio] [comando]"