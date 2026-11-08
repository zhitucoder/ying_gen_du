# AGENTS.md

## Project

影跟读 backend: import a video/audio (local upload or link) → ASR with timestamps → sentence segmentation → per-sentence mp3 clips + original video → client plays a sentence and records A/B. **v1 has no pronunciation scoring.**

`docs/技术实现方案.md` is the implementation baseline. Docs can lag code; trust `src/` and config when they conflict.

## Layout (all code lives in `src/`)

- `src/api/` — FastAPI app (`main.py`), routers (`routers/`), SQLAlchemy models, MinIO helpers.
- `src/worker/` — Celery app, media pipeline (`pipeline.py`), ffmpeg helpers, sentence splitting, ASR providers.
- `src/common/config.py` — all env settings (pydantic-settings, loads `.env`).
- `src/miniapp/` — uni-app (Vue3 + TS) frontend; H5 first, WeChat mini program later.
- `infra/docker-compose.yml` — MySQL / Redis / MinIO.
- `docs/` — design docs; `需求/01.项目需求.md` — original requirements.

## Environment

- Use repo-local `.venv` (created with `uv`, system Python 3.12.3). **Do not use conda.**
- Run every command from the repo root: `src` is the package root and `.env` is loaded relative to CWD.
- `.venv` and `.env` are gitignored. `requirements.txt` = top-level deps; `requirements.lock.txt` = pinned versions.
- This directory is **not a git repo**; do not assume git/PR workflows.

## Commands

```bash
# infra (MySQL/Redis/MinIO)
docker compose -f infra/docker-compose.yml up -d

# API
.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# worker (run exactly one)
.venv/bin/celery -A src.worker.celery_app:celery_app worker -l info -c 2

# no test/lint config exists; use these as the verification gate
.venv/bin/python -m compileall -q src
curl -s http://127.0.0.1:8000/health

# media GC (manual)
.venv/bin/python -m src.worker.gc
```

- No pytest / ruff / mypy configured. Verify changes with `compileall`, `/health`, and an upload → poll → `/segments` smoke test.
- Only run **one** Celery worker. Duplicate workers can consume tasks with stale code/config (this happened).

## Frontend

- `src/miniapp/` is **uni-app (Vue3 + TS)**, separate from the Python package. It targets H5 first, WeChat mini program later.
- From `src/miniapp/`: `npm install`, `npm run dev:h5` (port 5173), `npm run dev:mp-weixin` (open `dist/dev/mp-weixin` in WeChat DevTools).
- API base is `VITE_API_BASE_URL` (default `http://127.0.0.1:8000`); set it in `src/miniapp/.env`.
- H5 recording uses browser `MediaRecorder`; mini program uses `uni.getRecorderManager`. `manifest.json` currently has an empty WeChat AppID.
- WeChat DevTools needs “不校验合法域名” for local http API/MinIO.

## Services and ports

- MySQL `3307:3306` (host 3306 is used), DB/user/password all `yinggen`.
- Redis `6379`.
- MinIO API `9000`, console `9001`, bucket `yinggen`, credentials `minioadmin` / `minioadmin`.
- Images are `pgsty/minio:latest` + `pgsty/mc:latest` (bucket init container); this is not the official `minio/minio` image.

## Architecture invariants

- DB columns `audio_url` / `video_url` / `source_video_url` store **object keys, never URLs**. The API converts them to presigned URLs in `src/api/storage.py`; keep this invariant.
- Media is content-addressed: `media_assets.sha256` is unique; `media_asset_files` holds `original/proxy/audio`; `media_sources` maps URL/upload fingerprints to assets. `projects.media_asset_id` links projects, and `ref_count` tracks references.
- Original/proxy/audio are stored once per asset; per-sentence mp3s stay per project. Deleting a project decrements `ref_count`; GC is `src/worker/gc.py` (`python -m src.worker.gc`, 24h grace by default).
- Legacy projects may have `media_asset_id = NULL` and per-project `projects/{id}/source.mp4`; do not assume every project has an asset.
- Presigned URLs are signed against `MINIO_ENDPOINT`. For phone clients this endpoint must be reachable (not `127.0.0.1`).
- Tables are created by `Base.metadata.create_all()` in the FastAPI lifespan. There is **no Alembic**; schema changes need a manual migration (or drop/recreate in dev).
- `ffmpeg` / `ffprobe` must be on PATH. The pipeline decodes once to `full.wav`, slices segments from it, and transcodes a 720p H.264/AAC proxy.
- Task flow: `POST /api/tasks` or `/api/tasks/upload` → Redis/Celery → `src/worker/pipeline.py` → DB status/progress. Enqueue is best-effort; if Redis is down the project stays `queued`.

## ASR

- Factory: `src/worker/asr/__init__.py` (`mock`, `volcengine`, `tencent`); switch with `ASR_PROVIDER` in `.env`.
- Active provider: **Volcengine** (`ASR_VOLCENGINE_API_KEY`, resource `volc.seedasr.auc`). `src/worker/asr/volcengine.py` uses async `submit` + `query` and sends base64 `audio.data`, so MinIO does not need public access for ASR.
- `tencent.py` is a stub. Aliyun / iFlytek only have reserved env vars.
- The pipeline sends the 64k mp3 to ASR; the mock provider ignores the audio.

## Link import

- `yt-dlp` handles Bilibili / YouTube and similar.
- Douyin links use a Playwright resolver: `src/worker/douyin.py` → `src/worker/resolvers/douyin.js` (Node + `playwright` + Chromium). It opens the real page, captures `aweme_detail`, and downloads without user credentials.
- Requires `cd src/worker/resolvers && npm install` plus a Chromium binary (`npx playwright install chromium`, or an existing `~/.cache/ms-playwright/chromium-*`). `DOUYIN_RESOLVER_ENABLED=false` disables it.
- Do not fall back to `download_direct` for Douyin: unauthenticated HTTP returns HTML, not video.

## v1 scope — do not add unprompted

- No pronunciation scoring: `POST /api/segments/{id}/score` returns 501; `recordings.score` is reserved and unused.
- Recordings are uploaded to MinIO (not local-only).
- Auth: username/password + phone/SMS (PBKDF2, JWT with `token_version`). Endpoints: `/api/auth/{register,login,me}`, `/api/auth/sms/{send,register,login,reset-password,bind}`. Password reset bumps `token_version` and revokes old JWTs. WeChat login is **not** implemented yet.
- SMS: `src/api/sms` (mock default, tencent). Rate limits in Redis via Lua: 60s cooldown, 5/day/phone, 3/hour, plus IP/device caps. Codes are hashed in `sms_codes`; never log or return plaintext. `SMS_PROVIDER=mock` uses `SMS_MOCK_CODE` (default `123456`).
- `users` has `username/password_hash/phone/phone_verified_at/auth_type/token_version`; startup `ensure_schema()` adds them (no Alembic).
- Nicknames are globally unique. Defaults are generated per prefix (`学神01`, `学霸01`, ...) via `nickname_counters`; `users.nickname` has a unique index. `PATCH /api/auth/me` changes it. Startup `ensure_nickname_unique()` resolves empty/duplicate nicknames before adding the index.
- All project/recording queries are scoped by `user_id`; keep the ownership checks.
- Frontend login page is the first page; JWT lives in `yg_token`, 401 redirects to login.
- Code comments/docstrings are rejected by a hook unless they explain non-obvious algorithms. Keep code self-documenting.
