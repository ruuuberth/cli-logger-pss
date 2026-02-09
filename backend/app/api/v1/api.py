from fastapi import APIRouter
from app.api.v1.endpoints import items, ships, crews

api_router = APIRouter()
api_router.include_router(items.router, prefix="/items", tags=["items"])
api_router.include_router(ships.router, prefix="/ships", tags=["ships"])
api_router.include_router(crews.router, prefix="/crews", tags=["crews"])