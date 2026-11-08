from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import get_current_user
from src.api.models import Project, Segment, User
from src.api.schemas import ProjectOut, ProjectUpdate, SegmentOut, TranscriptOut
from src.api.storage import presigned_get

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _get_owned_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


def _sign(key: Optional[str]) -> Optional[str]:
    return presigned_get(key) if key else None


def _project_out(project: Project) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        title=project.title,
        status=project.status,
        progress=project.progress,
        duration_ms=project.duration_ms,
        cover_url=project.cover_url,
        source_url=project.source_url,
        video_url=_sign(project.source_video_url),
        created_at=project.created_at,
    )


def _segment_out(segment: Segment) -> SegmentOut:
    return SegmentOut(
        id=segment.id,
        idx=segment.idx,
        text=segment.text,
        start_ms=segment.start_ms,
        end_ms=segment.end_ms,
        audio_url=_sign(segment.audio_url),
        video_url=_sign(segment.video_url),
    )


@router.get("", response_model=list[ProjectOut])
def list_projects(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ProjectOut]:
    projects = db.scalars(
        select(Project)
        .where(Project.user_id == user.id)
        .order_by(Project.created_at.desc())
    ).all()
    return [_project_out(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    return _project_out(_get_owned_project(db, project_id, user))


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: int,
    body: ProjectUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectOut:
    project = _get_owned_project(db, project_id, user)
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="title cannot be empty")
    project.title = title
    db.commit()
    db.refresh(project)
    return _project_out(project)


@router.get("/{project_id}/transcript", response_model=TranscriptOut)
def get_transcript(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TranscriptOut:
    project = _get_owned_project(db, project_id, user)
    segments = db.scalars(
        select(Segment).where(Segment.project_id == project.id).order_by(Segment.idx)
    ).all()
    return TranscriptOut(
        project_id=project.id,
        title=project.title,
        duration_ms=project.duration_ms,
        segments=[_segment_out(s) for s in segments],
    )


@router.get("/{project_id}/segments", response_model=list[SegmentOut])
def list_segments(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SegmentOut]:
    project = _get_owned_project(db, project_id, user)
    segments = db.scalars(
        select(Segment).where(Segment.project_id == project.id).order_by(Segment.idx)
    ).all()
    return [_segment_out(s) for s in segments]


@router.get("/{project_id}/video")
def get_video(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    project = _get_owned_project(db, project_id, user)
    if not project.source_video_url:
        raise HTTPException(status_code=404, detail="video not available")
    return {"video_url": presigned_get(project.source_video_url)}
