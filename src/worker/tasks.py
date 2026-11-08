import logging

from src.worker.celery_app import celery_app
from src.worker.pipeline import run_pipeline

logger = logging.getLogger(__name__)


@celery_app.task(name="process_project")
def process_project(project_id: int) -> dict:
    run_pipeline(project_id)
    return {"project_id": project_id, "status": "done"}


@celery_app.task(name="gc_media_assets")
def gc_media_assets_task() -> dict:
    from src.worker.gc import gc_media_assets

    return {"deleted": gc_media_assets()}
