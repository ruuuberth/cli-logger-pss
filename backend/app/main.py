import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.api import api_router
from app.models.database import Base, engine

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="API para PixelStarships Logger"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir rutas de API
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.on_event("startup")
async def on_startup():
    """Create DB tables if they don't exist yet."""
    Base.metadata.create_all(bind=engine)

@app.get("/")
async def root():
    return {"message": "PixelStarships Logger API", "version": settings.VERSION}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
