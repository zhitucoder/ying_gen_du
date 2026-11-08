import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import get_current_user
from src.api.models import Project, Recording, Segment, User
from src.api.schemas import RecordingOut
from src.api.storage import presigned_get, upload_file
from src.common.config import settings

router = APIRouter(prefix="/api/segments", tags=["segments"])


def _get_owned_segment(db: Session, segment_id: int, user: User) -> Segment:
    segment = db.get(Segment, segment_id)
    if segment is None:
        raise HTTPException(status_code=404, detail="Segment not found")
    project = db.get(Project, segment.project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=404, detail="Segment not found")
    return segment


@router.post("/{segment_id}/recordings", response_model=RecordingOut)
async def upload_recording(
    segment_id: int,
    file: UploadFile = File(...),
    duration_ms: Optional[int] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordingOut:
    segment = _get_owned_segment(db, segment_id, user)

    ext = Path(file.filename or "recording.mp3").suffix.lower() or ".mp3"
    object_key = f"recordings/{user.id}/{segment.id}/{uuid.uuid4().hex}{ext}"

    tmp_dir = Path(settings.work_dir) / "recordings"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_path = tmp_dir / f"{uuid.uuid4().hex}{ext}"

    try:
        with local_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                out.write(chunk)
        upload_file(str(local_path), object_key, file.content_type or "audio/mpeg")
    finally:
        local_path.unlink(missing_ok=True)
        await file.close()

    recording = Recording(
        segment_id=segment.id,
        user_id=user.id,
        audio_url=object_key,
        duration_ms=duration_ms,
    )
    db.add(recording)
    db.commit()
    db.refresh(recording)

    return RecordingOut(
        id=recording.id,
        segment_id=recording.segment_id,
        audio_url=presigned_get(recording.audio_url),
        duration_ms=recording.duration_ms,
        created_at=recording.created_at,
    )


@router.post("/{segment_id}/score")
def score_segment(
    segment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _get_owned_segment(db, segment_id, user)
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="pronunciation scoring is not available in v1",
    )
