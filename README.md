# 影跟读（ying-gen-du）

影子跟读后端：导入视频/音频（本地上传或链接）→ ASR 带时间戳转写 → 分句 → 生成逐句 mp3 片段与原视频 → 客户端逐句播放、录音、A/B 对比。

> 第一版不做发音评分。技术方案见 `docs/技术实现方案.md`，开发约定见 `AGENTS.md`。

## 产品主流程

```
[粘贴链接] ─┐
            ├─▶ [创建跟读任务] ─▶ [解析链接并下载 / 读取已上传文件]
[上传本地视频] ─▶ [上传到 MinIO + 时长/格式校验] ─┘
                                        │
                                        ▼
                          [提取文案：ASR（带时间戳）]
                                        │
                                        ▼
                          [切句 + 生成单句音频 + 视频 720p 代理]
                                        │
                                        ▼
                              [句子列表 / 全文视图]
                                        │ 任选一句
                                        ▼
                                   [跟读页]
                                        │
                                        ▼
                [播放原句(视频 seek / 音频) / 录音 / A-B 对比]
```

核心页面：**首页**（粘贴链接 / 上传视频）、**句子列表 / 全文**（整篇文案、整篇播放、任选一句下钻）、**跟读页**（原句视频/音频 + 录音 + A/B 对比）。

## 目录结构

```
src/
├── api/       # FastAPI 服务（路由、模型、MinIO）
├── worker/    # Celery 异步任务与媒体流水线
├── common/    # 配置
└── miniapp/   # uni-app 前台（H5 / 微信小程序）
infra/         # docker-compose（MySQL / Redis / MinIO）
docs/          # 设计与接口文档
```

## 环境要求

- Python 3.12、[uv](https://docs.astral.sh/uv/)
- Node.js 18+ / npm（前台 uni-app + 抖音链接解析）
- Docker + Docker Compose
- `ffmpeg` / `ffprobe`（需在 PATH 中）

## 快速开始

### 1. 启动基础设施

```bash
docker compose -f infra/docker-compose.yml up -d
```

启动后：

| 服务 | 地址 | 账号 / 说明 |
|---|---|---|
| MySQL | `127.0.0.1:3307` | 库/用户/密码均为 `yinggen` |
| Redis | `127.0.0.1:6379` | 无密码 |
| MinIO API | `127.0.0.1:9000` | `minioadmin` / `minioadmin` |
| MinIO 控制台 | http://127.0.0.1:9001 | 同上 |

Bucket `yinggen` 会自动创建。宿主机 3306 已被占用，所以 MySQL 映射到 3307。

### 2. 配置环境变量

```bash
cp .env.example .env
```

默认 `ASR_PROVIDER=mock`，无需任何 Key 即可跑通。要接火山引擎：

```ini
ASR_PROVIDER=volcengine
ASR_VOLCENGINE_API_KEY=你的key
ASR_VOLCENGINE_RESOURCE_ID=volc.seedasr.auc
```

### 3. 创建虚拟环境并安装依赖

```bash
# 首次（其他人拿代码后）
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
```

> 依赖锁定版本可用 `requirements.lock.txt`。

抖音链接解析需要 Node 依赖与 Chromium：

```bash
cd src/worker/resolvers
npm install
npx playwright install chromium   # 首次需要；已有 Chromium 可跳过
cd ../../..
```

### 4. 启动服务

分别在两个终端执行（都在仓库根目录）：

```bash
# API
.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
```

```bash
# Worker（只运行一个）
.venv/bin/celery -A src.worker.celery_app:celery_app worker -l info -c 2
```

### 5. 启动前台（H5 / 微信小程序）

前台代码在 `src/miniapp`（uni-app + Vue3 + TS）。

```bash
cd src/miniapp
cp .env.example .env          # 可选，默认 http://127.0.0.1:8000
npm install

# H5（浏览器预览，推荐先跑这个）
npm run dev:h5                # http://localhost:5173

# 微信小程序（需要微信开发者工具与 AppID）
npm run dev:mp-weixin         # 用开发者工具打开 dist/dev/mp-weixin
```

- 微信开发者工具需勾选“不校验合法域名”，因为本地 API / MinIO 是 http + 127.0.0.1。
- 手机真机访问时，把 `VITE_API_BASE_URL` 与 `MINIO_ENDPOINT` 改成局域网可达地址。
- H5 录音使用浏览器麦克风（localhost / HTTPS 可用）；小程序使用 `RecorderManager`。

## 验证

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok","env":"dev"}
```

上传一个视频后轮询任务直至 `ready`，再拉取句子列表即可看到转写与逐句音频。

## 注意事项

- **必须在仓库根目录运行**：`src` 是包根，`.env` 按当前目录加载。
- **只运行一个 Celery Worker**：多个 Worker 可能用旧代码/旧配置消费任务。
- 数据库表在 API 启动时由 `create_all` 自动创建，暂无 Alembic；改表需手动迁移或重建。
- DB 中 `audio_url` / `video_url` 存的是对象 key，接口返回的是 MinIO 签名 URL。
- 抖音链接由 Playwright 无头浏览器解析（`src/worker/resolvers/douyin.js`），无需登录；B站/YouTube 等走 `yt-dlp`。可通过 `DOUYIN_RESOLVER_ENABLED=false` 关闭。
- `.env` 已被 `.gitignore` 排除，请勿提交密钥。

## 相关文档

- `docs/技术实现方案.md` — 技术实现方案
- `docs/技术方案-v1.md` — v1 收敛方案
- `docs/火山语音API.MD` — 火山 ASR 接口说明
- `docs/云语音识别收费标准.md` — 各厂商 ASR 价格
