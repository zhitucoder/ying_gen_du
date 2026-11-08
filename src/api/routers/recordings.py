from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import get_current_user
from src.api.models import Project, Recording, Segment, User
from src.api.schemas import RecordingOut
from src.api.storage import presigned_get

router = APIRouter(prefix="/api/recordings", tags=["recordings"])


@router.get("/{recording_id}", response_model=RecordingOut)
def get_recording(
    recording_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RecordingOut:
    recording = db.get(Recording, recording_id)
    if recording is None or recording.user_id != user.id:
        raise HTTPException(status_code=404, detail="Recording not found")

    return RecordingOut(
        id=recording.id,
        segment_id=recording.segment_id,
        audio_url=presigned_get(recording.audio_url),
        duration_ms=recording.duration_ms,
        created_at=recording.created_at,
    )
