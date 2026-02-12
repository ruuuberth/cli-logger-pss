from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.pss_service import (
    PSSAuthenticationError,
    PSSFeatureNotSupportedError,
    PSSService,
)

router = APIRouter()


class EmailLoginRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=1)
    device_key: str | None = None


class RefreshLoginRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)
    device_key: str | None = None


@router.post("/login-email")
async def login_with_email_password(payload: EmailLoginRequest, db: Session = Depends(get_db)):
    """Login por email/password para obtener access token reutilizable en endpoints protegidos."""
    try:
        pss_service = PSSService(db)
        token_data = await pss_service.login_with_email_password(
            email=payload.email,
            password=payload.password,
            device_key=payload.device_key,
        )
        return {"data": token_data}
    except PSSFeatureNotSupportedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except PSSAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/login-refresh")
async def login_with_refresh_token(payload: RefreshLoginRequest, db: Session = Depends(get_db)):
    """Intercambiar refresh token por access token."""
    try:
        pss_service = PSSService(db)
        token_data = await pss_service.login_with_refresh_token(
            refresh_token=payload.refresh_token,
            device_key=payload.device_key,
        )
        return {"data": token_data}
    except PSSFeatureNotSupportedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except PSSAuthenticationError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
