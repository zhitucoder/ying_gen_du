import hashlib
import mimetypes
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.models import MediaAsset, MediaAssetFile, MediaSource, Project
from src.api.storage import upload_file
from src.common.config import settings

ALLOWED_EXTENSIONS = {".mp4", ".webm", ".mkv", ".mov", ".m4a", ".mp3", ".wav", ".ogg"}


def compute_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def asset_prefix(sha256: str) -> str:
    base = settings.media_asset_prefix.strip("/")
    return f"{base}/{sha256[:2]}/{sha256}"


def asset_object_key(sha256: str, kind: str, ext: str = ".mp4") -> str:
    prefix = asset_prefix(sha256)
    if kind == "original":
        safe_ext = ext.lower() if ext.lower() in ALLOWED_EXTENSIONS else ".bin"
        return f"{prefix}/original{safe_ext}"
    if kind == "proxy":
        return f"{prefix}/proxy.mp4"
    if kind == "audio":
        return f"{prefix}/audio.mp3"
    if kind == "cover":
        return f"{prefix}/cover.jpg"
    return f"{prefix}/{kind}"


def find_asset_by_sha(db: Session, sha256: str) -> Optional[MediaAsset]:
    return db.scalar(select(MediaAsset).where(MediaAsset.sha256 == sha256))


def get_asset_file(db: Session, asset_id: int, kind: str) -> Optional[MediaAssetFile]:
    return db.scalar(
        select(MediaAssetFile).where(
            MediaAssetFile.asset_id == asset_id,
            MediaAssetFile.kind == kind,
        )
    )


def get_or_create_asset(
    db: Session,
    *,
    sha256: str,
    size_bytes: int,
    mime_type: Optional[str],
    title: Optional[str],
    local_path: str | Path,
    ext: str,
) -> MediaAsset:
    existing = find_asset_by_sha(db, sha256)
    if existing is not None:
        return existing

    object_key = asset_object_key(sha256, "original", ext)
    content_type = mime_type or mimetypes.guess_type(str(local_path))[0]
    upload_file(str(local_path), object_key, content_type or "application/octet-stream")

    asset = MediaAsset(
        sha256=sha256,
        size_bytes=size_bytes,
        mime_type=content_type,
        title=title,
        status="active",
        ref_count=0,
    )
    db.add(asset)
    try:
        db.flush()
        db.add(
            MediaAssetFile(
                asset_id=asset.id,
                kind="original",
                object_key=object_key,
                size_bytes=size_bytes,
            )
        )
        db.commit()
        return asset
    except IntegrityError:
        db.rollback()
        existing = find_asset_by_sha(db, sha256)
        if existing is not None:
            return existing
        raise


def upsert_asset_file(
    db: Session,
    asset: MediaAsset,
    kind: str,
    object_key: str,
    size_bytes: Optional[int] = None,
) -> MediaAssetFile:
    existing = get_asset_file(db, asset.id, kind)
    if existing is not None:
        return existing

    record = MediaAssetFile(
        asset_id=asset.id,
        kind=kind,
        object_key=object_key,
        size_bytes=size_bytes,
    )
    db.add(record)
    try:
        db.commit()
        return record
    except IntegrityError:
        db.rollback()
        existing = get_asset_file(db, asset.id, kind)
        if existing is not None:
            return existing
        raise


def normalize_source_url(url: str) -> str:
    parts = urlsplit(url.strip())
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), path, parts.query, "")
    )


def url_fingerprint(url: str) -> str:
    return f"url:{hashlib.sha256(normalize_source_url(url).encode()).hexdigest()}"


def upload_fingerprint(sha256: str) -> str:
    return f"upload:{sha256}"


def find_asset_by_source(db: Session, fingerprint: str) -> Optional[MediaAsset]:
    source = db.scalar(
        select(MediaSource).where(MediaSource.fingerprint == fingerprint)
    )
    if source is None:
        return None
    asset = db.get(MediaAsset, source.asset_id)
    if asset is None or asset.status != "active":
        return None
    return asset


def add_source(db: Session, fingerprint: str, asset_id: int) -> None:
    existing = db.scalar(
        select(MediaSource).where(MediaSource.fingerprint == fingerprint)
    )
    if existing is not None:
        return
    db.add(MediaSource(fingerprint=fingerprint, asset_id=asset_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()


def increment_asset(db: Session, asset_id: int) -> bool:
    result = db.execute(
        update(MediaAsset)
        .where(MediaAsset.id == asset_id, MediaAsset.status == "active")
        .values(ref_count=MediaAsset.ref_count + 1, last_used_at=datetime.utcnow())
    )
    db.commit()
    return bool(result.rowcount)


def decrement_asset(db: Session, asset_id: int) -> None:
    db.execute(
        update(MediaAsset)
        .where(MediaAsset.id == asset_id, MediaAsset.ref_count > 0)
        .values(ref_count=MediaAsset.ref_count - 1, last_used_at=datetime.utcnow())
    )
    db.commit()


def link_project_asset(db: Session, project: Project, asset: MediaAsset) -> None:
    if project.media_asset_id == asset.id:
        return
    if project.media_asset_id:
        decrement_asset(db, project.media_asset_id)
    if not increment_asset(db, asset.id):
        raise RuntimeError("media asset is no longer available")
    project.media_asset_id = asset.id
    db.commit()


def unlink_project_asset(db: Session, project: Project) -> None:
    if not project.media_asset_id:
        return
    decrement_asset(db, project.media_asset_id)
    project.media_asset_id = None
    db.commit()
