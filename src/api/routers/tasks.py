import logging
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.db import get_db
from src.api.deps import get_current_user
from src.api.media_assets import (
    add_source,
    compute_sha256,
    get_asset_file,
    get_or_create_asset,
    link_project_asset,
    normalize_source_url,
    upload_fingerprint,
)
from src.api.models import Project, User
from src.api.schemas import TaskCreateRequest, TaskCreated, TaskStatus
from src.api.storage import upload_file
from src.common.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def enqueue_project(project_id: int) -> None:
    """Best-effort enqueue so a broker hiccup does not fail the HTTP request."""
    try:
        from src.worker.tasks import process_project

        process_project.delay(project_id)
    except Exception:  # pragma: no cover - depends on broker availability
        logger.exception("failed to enqueue project %s", project_id)


def _get_owned_project(db: Session, project_id: int, user: User) -> Project:
    project = db.get(Project, project_id)
    if project is None or project.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return project


@router.post("", response_model=TaskCreated)
def create_link_task(
    body: TaskCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskCreated:
    if not body.url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="url must be http(s)")

    source_url = body.url.strip()
    target = normalize_source_url(source_url)
    existing = next(
        (
            item
            for item in db.scalars(
                select(Project)
                .where(
                    Project.user_id == user.id,
                    Project.source_type == "link",
                )
                .order_by(Project.created_at.desc())
            ).all()
            if item.source_url and normalize_source_url(item.source_url) == target
        ),
        None,
    )
    if existing is not None:
        return TaskCreated(
            task_id=existing.id,
            status=existing.status,
            existing=True,
            title=existing.title,
        )

    project = Project(
        user_id=user.id,
        source_type="link",
        source_url=source_url,
        title=body.title,
        status="queued",
        progress=0,
        video_status="none",
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    enqueue_project(project.id)
    return TaskCreated(task_id=project.id, status=project.status)


@router.post("/upload", response_model=TaskCreated)
async def create_upload_task(
    file: UploadFile = File(...),
    title: Optional[str] = Form(default=None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskCreated:
    ext = Path(file.filename or "video.mp4").suffix.lower() or ".mp4"

    upload_dir = Path(settings.work_dir) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    local_path = upload_dir / f"{uuid.uuid4().hex}{ext}"

    size = 0
    limit = settings.max_upload_mb * 1024 * 1024
    asset = None
    object_key = ""
    try:
        with local_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > limit:
                    raise HTTPException(
                        status_code=413,
                        detail=f"file exceeds {settings.max_upload_mb}MB",
                    )
                out.write(chunk)

        if settings.media_dedup_enabled:
            sha256 = compute_sha256(local_path)
            asset = get_or_create_asset(
                db,
                sha256=sha256,
                size_bytes=size,
                mime_type=file.content_type,
                title=title or file.filename,
                local_path=local_path,
                ext=ext,
            )
            original = get_asset_file(db, asset.id, "original")
            if original is None:
                raise HTTPException(status_code=500, detail="asset original missing")
            object_key = original.object_key
            add_source(db, upload_fingerprint(sha256), asset.id)
        else:
            object_key = f"uploads/{user.id}/{uuid.uuid4().hex}{ext}"
            upload_file(str(local_path), object_key, file.content_type)

        project = Project(
            user_id=user.id,
            source_type="upload",
            source_video_url=object_key,
            title=title or file.filename,
            status="queued",
            progress=0,
            video_status="processing",
        )
        db.add(project)
        db.flush()
        if asset is not None:
            link_project_asset(db, project, asset)
        db.commit()
        db.refresh(project)
    finally:
        local_path.unlink(missing_ok=True)
        await file.close()

    enqueue_project(project.id)
    return TaskCreated(task_id=project.id, status=project.status)


@router.get("/{task_id}", response_model=TaskStatus)
def get_task(
    task_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TaskStatus:
    project = _get_owned_project(db, task_id, user)
    return TaskStatus(
        task_id=project.id,
        status=project.status,
        progress=project.progress,
        error_msg=project.error_msg,
        title=project.title,
        duration_ms=project.duration_ms,
    )
