#!/bin/bash

echo "🚀 Inicializando PixelStarships Logger..."

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 no encontrado. Por favor instala Python 3.11+"
    exit 1
fi

# Verificar Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js no encontrado. Por favor instala Node.js 16+"
    exit 1
fi

# Configurar backend
echo "📦 Configurando backend..."
cd backend

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "🔧 Creando entorno virtual..."
    python3 -m venv venv
fi

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias
echo "📥 Instalando dependencias de Python..."
pip install -r requirements.txt

# Crear base de datos
echo "🗄️ Creando base de datos..."
python -c "
from app.models.database import engine, Base
from app.models.pss_models import ItemDesign, ShipDesign, CrewDesign
Base.metadata.create_all(bind=engine)
print('✅ Base de datos creada exitosamente')
"

cd ..

# Configurar frontend
echo "📦 Configurando frontend..."
cd frontend

# Instalar dependencias
echo "📥 Instalando dependencias de Node.js..."
npm install

cd ..

echo "✅ ¡Inicialización completada!"
echo ""
echo "🎯 Para iniciar el proyecto:"
echo "1. Backend: cd backend && source venv/bin/activate && uvicorn app.main:app --reload"
echo "2. Frontend: cd frontend && npm start"
echo "3. Electron: cd frontend && npm run electron-dev"
echo ""
echo "🌐 El backend estará disponible en: http://localhost:8000"
echo "🌐 El frontend estará disponible en: http://localhost:3000"
echo "📖 API docs: http://localhost:8000/docs"