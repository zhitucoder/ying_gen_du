# 影跟读（ying-gen-du）

> 把任意视频变成逐句跟读素材：导入链接或本地视频 → 自动转写并分句 → 逐句播放、录音、A/B 对比。

**English:** Turn any video into sentence-by-sentence shadowing practice. Import a link or local video, auto-transcribe with timestamps, split it into sentence clips, and practice with A/B recording — built with FastAPI, Celery, uni-app, MySQL, Redis and MinIO.

---

## 它解决什么问题

传统影子跟读要手动暂停、拖进度条、反复找一句话的起止点。影跟读把这件事自动化：

1. 粘贴一个视频链接，或上传本地视频；
2. 服务端自动提取音频、转写带时间戳的字幕、切成一句一句；
3. 生成逐句音频片段与原视频代理；
4. 在全文里任选一句，反复听原声、跟读录音、A/B 对比。

适合英语启蒙、口语练习、听力精听、影子跟读等场景。

## 核心功能

- **双入口导入**：视频链接（抖音 / B站 / YouTube 等）+ 本地视频上传
- **带时间戳 ASR**：火山引擎豆包大模型，返回句级/词级时间戳
- **自动分句**：按标点 + 时长 + 字数切分，生成逐句 mp3
- **全文视图**：完整文案逐句展示，任选一句下钻
- **逐句跟读**：原声播放（视频 seek 或音频片段）、录音、回放
- **A/B 对比**：原句 ↔ 我的录音，支持循环与逐句切换
- **视频播放**：原视频整段播放、播放时高亮当前句
- **改标题**：用户可管理自己的跟读项目
- **多端前端**：uni-app（Vue3 + TS），H5 优先，可打包微信小程序

> 第一版**不做发音评分**，只做原声与录音的听感对比。

## 技术架构

```
┌──────────────────────────────┐
│   前台: uni-app (Vue3 + TS)    │
│   H5 / 微信小程序               │
└──────────────┬───────────────┘
               │ HTTPS / JSON
┌──────────────▼───────────────┐
│        FastAPI (JWT)          │
│  任务 / 项目 / 句子 / 录音      │
└──────┬───────────────┬───────┘
       │               │
   MySQL 8.0        Redis
                       │
              ┌────────▼─────────┐
              │   Celery Worker   │
              │ ffmpeg / yt-dlp   │
              │ Playwright(抖音)   │
              └────────┬─────────┘
                       │
              ┌────────▼─────────┐
              │ MinIO + 签名 URL  │
              └────────┬─────────┘
                       │
              ┌────────▼─────────┐
              │ 火山引擎 ASR       │
              └──────────────────┘
```

## 技术栈

| 层 | 选型 |
|---|---|
| 前台 | uni-app（Vue3 + TypeScript） |
| API | Python 3.12 + FastAPI |
| 异步任务 | Celery + Redis |
| 数据库 | MySQL 8.0 |
| 对象存储 | MinIO（S3 兼容；生产可换 OSS/COS） |
| 媒体处理 | ffmpeg / ffprobe |
| 链接解析 | yt-dlp + Playwright（抖音） |
| ASR | 火山引擎豆包（可插拔：Mock / 腾讯） |
| 前端构建 | Vite |

## 快速开始

```bash
# 1. 基础设施
docker compose -f infra/docker-compose.yml up -d

# 2. 后端
cp .env.example .env
uv venv .venv --python 3.12
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/uvicorn src.api.main:app --host 0.0.0.0 --port 8000
.venv/bin/celery -A src.worker.celery_app:celery_app worker -l info -c 2

# 3. 前台（H5）
cd src/miniapp
npm install
npm run dev:h5   # http://localhost:5173
```

抖音链接解析额外需要：

```bash
cd src/worker/resolvers
npm install
npx playwright install chromium
```

详细说明见 [README.md](./README.md) 与 [AGENTS.md](./AGENTS.md)。

## 项目结构

```
src/
├── api/        # FastAPI 服务
├── worker/     # Celery 流水线与媒体处理
├── common/     # 配置
└── miniapp/    # uni-app 前台
infra/          # MySQL / Redis / MinIO
docs/           # 设计与接口文档
```

## 当前状态

- ✅ 后端 MVP：链接/上传、ASR、分句切片、视频代理、录音、改名
- ✅ H5 前台：首页、进度、全文、跟读、录音、A/B
- ✅ 微信小程序构建通过（需填 AppID 后真机验证）
- 🚧 生产化待补：真实微信登录、限流/配额、内容审核、删除/分页、测试与监控

## Roadmap

- 删除项目、分页与搜索
- 微信登录与用户体系
- 内容审核与调用限额
- 离线缓存、学习打卡
- 发音评分（可选，接入评测 API）
- 自建 Whisper/FunASR 降本

## 合规声明

本项目仅用于**用户自己提供、且拥有使用权的内容**的学习工具。请勿用于批量下载、破解付费内容或去除水印；请遵守各平台服务条款与版权规定。视频号等强鉴权内容不在支持范围内。
