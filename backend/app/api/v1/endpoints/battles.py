from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.pss_service import PSSService

router = APIRouter()


@router.get("/recent")
async def get_user_recent_battles(
    username: str = Query(..., min_length=1, description="Nombre de usuario de Pixel Starships"),
    limit: int = Query(10, ge=1, le=50, description="Cantidad maxima de batallas a retornar"),
    db: Session = Depends(get_db),
):
    """Obtener las batallas mas recientes de un usuario."""
    try:
        pss_service = PSSService(db)
        normalized_username = username.strip()
        battles = await pss_service.get_user_recent_battles(normalized_username, limit)
        return {"data": battles, "count": len(battles), "username": normalized_username}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
