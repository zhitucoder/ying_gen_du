import logging
from datetime import datetime, timedelta

from sqlalchemy import and_, or_, select

from src.api.db import SessionLocal
from src.api.models import MediaAsset, MediaAssetFile
from src.api.storage import delete_object
from src.common.config import settings

logger = logging.getLogger(__name__)


def gc_media_assets(grace_seconds: int | None = None) -> int:
    grace = settings.media_gc_grace_seconds if grace_seconds is None else grace_seconds
    cutoff = datetime.utcnow() - timedelta(seconds=grace)

    deleted = 0
    with SessionLocal() as db:
        candidates = db.scalars(
            select(MediaAsset).where(
                MediaAsset.ref_count == 0,
                MediaAsset.status == "active",
                or_(
                    MediaAsset.last_used_at < cutoff,
                    and_(
                        MediaAsset.last_used_at.is_(None),
                        MediaAsset.created_at < cutoff,
                    ),
                ),
            )
        ).all()

        for candidate in candidates:
            asset = db.scalar(
                select(MediaAsset)
                .where(MediaAsset.id == candidate.id)
                .with_for_update()
            )
            if asset is None or asset.ref_count > 0:
                continue

            files = db.scalars(
                select(MediaAssetFile).where(MediaAssetFile.asset_id == asset.id)
            ).all()
            for file in files:
                delete_object(file.object_key)
            db.delete(asset)
            db.commit()
            deleted += 1
            logger.info("gc deleted media asset %s", candidate.id)

    return deleted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print({"deleted": gc_media_assets()})
