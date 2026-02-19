from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.pss_service import PSSAuthenticationError, PSSFeatureNotSupportedError, PSSService

router = APIRouter()


@router.get("/report")
async def get_battle_report(
    battle_id: int = Query(..., ge=1, description="BattleId del reporte (BattleService/GetBattle3)"),
    access_token: str | None = Query(
        None,
        description="Access token para descargar el reporte XML desde API oficial",
    ),
    force_refresh: bool = Query(
        False,
        description="Si es true, obliga descarga remota e ignora cache (memoria/DB) cuando sea posible",
    ),
    ttl_seconds: int | None = Query(
        None,
        ge=0,
        description="TTL opcional del cache en memoria para este request",
    ),
    db: Session = Depends(get_db),
):
    """Obtener y persistir reporte XML de una batalla individual."""
    try:
        pss_service = PSSService(db)
        report = await pss_service.get_battle_report(
            battle_id=battle_id,
            access_token=access_token,
            force_refresh=force_refresh,
            ttl_seconds=ttl_seconds,
        )
        return {"data": report}
    except PSSFeatureNotSupportedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except PSSAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stored")
async def get_stored_battle_ids(
    limit: int = Query(200, ge=1, le=1000, description="Cantidad maxima de IDs de batalla a retornar"),
    offset: int = Query(0, ge=0, description="Offset para paginacion"),
    db: Session = Depends(get_db),
):
    """Listar IDs de batallas almacenados localmente para inspeccion rapida."""
    try:
        pss_service = PSSService(db)
        return pss_service.list_stored_battle_ids(limit=limit, offset=offset)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
