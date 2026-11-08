import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.db import ensure_schema, init_db
from src.api.routers import auth, projects, recordings, segments, tasks
from src.api.storage import ensure_bucket
from src.common.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    ensure_schema()
    try:
        ensure_bucket()
    except Exception:  # pragma: no cover - storage may be down in dev
        logger.exception("failed to ensure MinIO bucket at startup")
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(segments.router)
app.include_router(recordings.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "env": settings.env}
