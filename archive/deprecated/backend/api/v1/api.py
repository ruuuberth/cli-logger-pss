from fastapi import APIRouter
from app.api.v1.endpoints import auth, battles, crews, items, local_data, ships

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(ships.router, prefix="/ships", tags=["ships"])
api_router.include_router(crews.router, prefix="/crews", tags=["crews"])
api_router.include_router(battles.router, prefix="/battles", tags=["battles"])
api_router.include_router(local_data.router, prefix="/local-data", tags=["local-data"])
