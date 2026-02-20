from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.services.pss_service import PSSService
from app.models.database import get_db

router = APIRouter()

@router.get("/designs")
async def get_crew_designs(
    refresh: bool = Query(False, description="Forzar refresh desde la API remota"),
    ttl_seconds: Optional[int] = Query(
        None, ge=0, description="TTL de cache en segundos para esta petición"
    ),
    db: Session = Depends(get_db)
):
    """Obtener todos los diseños de tripulación de PixelStarships"""
    try:
        pss_service = PSSService(db)
        designs = await pss_service.get_crew_designs(
            force_refresh=refresh,
            ttl_seconds=ttl_seconds,
        )
        return {"data": designs, "count": len(designs)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/designs/{crew_id}")
async def get_crew_design(crew_id: int, db: Session = Depends(get_db)):
    """Obtener un diseño de tripulación específico"""
    try:
        pss_service = PSSService(db)
        design = await pss_service.get_crew_design(crew_id)
        if not design:
            raise HTTPException(status_code=404, detail="Crew design not found")
        return {"data": design}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
