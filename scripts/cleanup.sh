#!/bin/bash

echo "🧹 Limpiando contenedores Docker de PixelStarships Logger..."

# Opciones
# Determinar el comando de Docker Compose
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    echo "❌ Docker Compose no encontrado."
    exit 1
fi

case "${1:-all}" in
    "all")
        echo "🗑️  Eliminando todos los contenedores, imágenes y volúmenes..."
        $DOCKER_COMPOSE_CMD down -v --rmi all
        $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml down -v --rmi all
        docker system prune -f
        ;;
    "prod")
        echo "🗑️  Limpiando entorno de producción..."
        $DOCKER_COMPOSE_CMD down -v --rmi all
        ;;
    "dev")
        echo "🗑️  Limpiando entorno de desarrollo..."
        $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml down -v --rmi all
        ;;
    "containers")
        echo "🗑️  Eliminando solo contenedores..."
        $DOCKER_COMPOSE_CMD down
        $DOCKER_COMPOSE_CMD -f docker-compose.dev.yml down
        ;;
    "images")
        echo "🗑️  Eliminando imágenes Docker..."
        docker images | grep 'pss_' | awk '{print $3}' | xargs docker rmi -f
        ;;
    "volumes")
        echo "🗑️  Eliminando volúmenes..."
        docker volume ls | grep 'logger_pss' | awk '{print $2}' | xargs docker volume rm
        ;;
    *)
        echo "Uso: $0 [all|prod|dev|containers|images|volumes]"
        echo ""
        echo "Opciones:"
        echo "  all        - Eliminar todo (contenedores, imágenes, volúmenes)"
        echo "  prod       - Limpiar solo entorno de producción"
        echo "  dev        - Limpiar solo entorno de desarrollo"
        echo "  containers - Eliminar solo contenedores"
        echo "  images     - Eliminar solo imágenes"
        echo "  volumes    - Eliminar solo volúmenes"
        exit 1
        ;;
esac

echo "✅ ¡Limpieza completada!"