from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.pss_service import PSSFeatureNotSupportedError, PSSService

router = APIRouter()


@router.get("/recent")
async def get_user_recent_battles(
    username: str = Query(..., min_length=1, description="Nombre de usuario de Pixel Starships"),
    limit: int = Query(10, ge=1, le=50, description="Cantidad maxima de batallas a retornar"),
    access_token: str | None = Query(
        None,
        description="Access token opcional para endpoints que requieren autenticacion",
    ),
    refresh_token: str | None = Query(
        None,
        description="Refresh token opcional; se intentara convertir a access token si es posible",
    ),
    device_key: str | None = Query(
        None,
        description="Device key opcional para conversion de refresh token",
    ),
    db: Session = Depends(get_db),
):
    """Obtener las batallas mas recientes de un usuario."""
    try:
        pss_service = PSSService(db)
        normalized_username = username.strip()
        battles = await pss_service.get_user_recent_battles(
            normalized_username,
            limit,
            access_token=access_token,
            refresh_token=refresh_token,
            device_key=device_key,
        )
        return {"data": battles, "count": len(battles), "username": normalized_username}
    except PSSFeatureNotSupportedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
