import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from src.api.db import SessionLocal
from src.api.models import Project, Segment
from src.api.storage import upload_file
from src.common.config import settings
from src.worker.asr import get_asr_provider
from src.worker.media import (
    download_direct,
    download_with_ytdlp,
    extract_audio,
    ffprobe_duration_ms,
    has_video_stream,
    slice_audio,
    transcode_video,
)
from src.worker.segmentation import normalize_segments

logger = logging.getLogger(__name__)


def _update(project: Project, db, *, status: str | None = None, progress: int | None = None, **fields) -> None:
    if status is not None:
        project.status = status
    if progress is not None:
        project.progress = progress
    for key, value in fields.items():
        setattr(project, key, value)
    db.commit()


def _prepare_source(project: Project, work_dir: Path, db) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)

    if project.source_type == "upload":
        key = project.source_video_url
        if not key:
            raise RuntimeError("upload project has no source object")
        ext = Path(key).suffix or ".mp4"
        local = work_dir / f"source{ext}"
        from src.api.storage import download_file

        _update(project, db, status="downloading", progress=10)
        download_file(key, str(local))
        return local

    if not project.source_url:
        raise RuntimeError("link project has no source url")

    _update(project, db, status="downloading", progress=10)
    if "douyin.com" in project.source_url:
        from src.worker.douyin import download_douyin

        dest = work_dir / "source.mp4"
        meta = download_douyin(project.source_url, dest)
        if not project.title and meta.get("title"):
            project.title = meta["title"]
            db.commit()
        return dest

    try:
        return download_with_ytdlp(project.source_url, work_dir)
    except Exception:
        logger.exception("yt-dlp failed, falling back to direct download")
        return download_direct(project.source_url, work_dir / "source.mp4")


def run_pipeline(project_id: int) -> None:
    db = SessionLocal()
    project = db.get(Project, project_id)
    if project is None:
        logger.warning("project %s not found", project_id)
        db.close()
        return

    work_dir = Path(settings.work_dir) / f"project_{project_id}"
    try:
        source = _prepare_source(project, work_dir, db)

        duration_ms = ffprobe_duration_ms(source)
        max_ms = settings.max_video_seconds * 1000
        if duration_ms > max_ms:
            raise RuntimeError(
                f"video too long: {duration_ms / 1000:.0f}s > {settings.max_video_seconds}s"
            )

        _update(
            project,
            db,
            status="extracting",
            progress=30,
            duration_ms=duration_ms,
        )

        wav_path = work_dir / "full.wav"
        mp3_path = work_dir / "full.mp3"
        extract_audio(source, wav_path, mp3_path)
        upload_file(str(mp3_path), f"projects/{project.id}/audio.mp3", "audio/mpeg")

        _update(project, db, status="transcribing", progress=50)
        provider = get_asr_provider()
        asr_segments = provider.transcribe(str(mp3_path), duration_ms=duration_ms)

        _update(project, db, status="segmenting", progress=75)
        segments = normalize_segments(asr_segments, duration_ms=duration_ms)

        for idx, segment in enumerate(segments):
            seg_path = work_dir / f"seg_{idx}.mp3"
            slice_audio(wav_path, segment.start_ms, segment.end_ms, seg_path)
            object_key = f"projects/{project.id}/segments/{idx}.mp3"
            upload_file(str(seg_path), object_key, "audio/mpeg")
            db.add(
                Segment(
                    project_id=project.id,
                    idx=idx,
                    text=segment.text,
                    start_ms=segment.start_ms,
                    end_ms=segment.end_ms,
                    audio_url=object_key,
                )
            )
        db.commit()

        video_key = project.source_video_url
        if settings.transcode_video and has_video_stream(source):
            proxy_path = work_dir / "proxy.mp4"
            transcode_video(source, proxy_path)
            proxy_key = f"projects/{project.id}/source.mp4"
            upload_file(str(proxy_path), proxy_key, "video/mp4")
            video_key = proxy_key

        _update(
            project,
            db,
            status="ready",
            progress=100,
            source_video_url=video_key,
            video_status="ready" if video_key else "none",
            video_expire_at=datetime.utcnow()
            + timedelta(days=settings.video_retention_days),
        )
        logger.info("project %s ready with %d segments", project_id, len(segments))

    except Exception as exc:
        logger.exception("project %s failed", project_id)
        db.rollback()
        failed = db.get(Project, project_id)
        if failed is not None:
            failed.status = "failed"
            failed.progress = 0
            failed.error_msg = str(exc)[:1000]
            db.commit()
        raise
    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        db.close()
