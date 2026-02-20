import hashlib
from typing import List

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.pss_models import ImportedGameFile

router = APIRouter()

MAX_FILES_PER_REQUEST = 300
MAX_FILE_SIZE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_SIZE_BYTES = 20 * 1024 * 1024


@router.post("/import-game-files")
async def import_game_files(
    files: List[UploadFile] = File(..., description="Archivos exportados desde SavySoda/Pixel Starships"),
    source_dir: str | None = Form(None, description="Ruta base detectada en cliente"),
    relative_paths: List[str] = Form(default=[]),
    db: Session = Depends(get_db),
):
    if len(files) == 0:
        raise HTTPException(status_code=400, detail="No se recibieron archivos.")

    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Se permiten maximo {MAX_FILES_PER_REQUEST} archivos por importacion.",
        )

    imported = 0
    updated = 0
    skipped = 0
    total_bytes = 0

    try:
        for index, upload in enumerate(files):
            raw = await upload.read()
            size = len(raw)
            total_bytes += size

            if size == 0:
                skipped += 1
                continue

            if size > MAX_FILE_SIZE_BYTES:
                skipped += 1
                continue

            if total_bytes > MAX_TOTAL_SIZE_BYTES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Tamano total excedido. Maximo permitido: {MAX_TOTAL_SIZE_BYTES} bytes.",
                )

            content_hash = hashlib.sha256(raw).hexdigest()
            content_text = raw.decode("utf-8", errors="replace")
            relative_path = relative_paths[index] if index < len(relative_paths) else upload.filename
            file_name = (upload.filename or "archivo_sin_nombre")[:255]
            file_ext = ""
            if "." in file_name:
                file_ext = file_name.rsplit(".", 1)[-1].lower()[:32]

            existing = (
                db.query(ImportedGameFile)
                .filter(ImportedGameFile.content_hash == content_hash)
                .first()
            )

            if existing:
                existing.source_dir = (source_dir or existing.source_dir or "")[:1024]
                existing.relative_path = str(relative_path or existing.relative_path or "")[:2048]
                existing.file_name = file_name
                existing.file_ext = file_ext
                existing.file_size = size
                existing.content_text = content_text
                updated += 1
                continue

            row = ImportedGameFile(
                source_dir=(source_dir or "")[:1024],
                relative_path=str(relative_path or "")[:2048],
                file_name=file_name,
                file_ext=file_ext,
                file_size=size,
                content_hash=content_hash,
                content_text=content_text,
            )
            db.add(row)
            imported += 1

        db.commit()

        return {
            "data": {
                "source_dir": source_dir,
                "received_files": len(files),
                "imported": imported,
                "updated": updated,
                "skipped": skipped,
                "total_bytes": total_bytes,
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))
