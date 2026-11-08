# 影跟读 · APP 技术实现方案（Android / iOS）

> 版本：v0.1（初稿）
> 日期：2026-11-07
> 范围：面向 Android / iOS 原生安装包的影子跟读 App 架构设计
> 关联：小程序版方案见 `docs/技术实现方案.md`

---

## 1. 与小程序版的差异

| 维度 | 微信小程序版 | App 版（本文档） |
|---|---|---|
| 分发 | 免安装、扫码即用 | 应用商店安装，需上架/签名 |
| 包体 | 主包 ≤2MB，分包 ~20MB | 安装包 15–30MB，需重点优化 |
| 系统能力 | 受限（录音/后台/分享有限） | 完整（后台任务、分享扩展、推送、锁屏控制） |
| 入口体验 | 复制链接 → 小程序内粘贴 | **抖音"分享"直接选本 App**（Share Extension / Intent） |
| 离线能力 | 弱 | 强（本地缓存句子音频/录音，可离线跟读） |
| 账号 | 微信登录 | 设备登录 / 手机号 / 微信 SDK（可选） |
| 任务通知 | 轮询 | 推送（APNs / FCM），后台完成提醒 |
| 更新 | 随平台 | 应用商店；谨慎热更新 |

> **核心不变**：下载、转码、ASR、分句、切片仍全部在服务端完成，App 也不内置 ffmpeg / ASR 模型。这是控制包体的根本。
>
> **共同核心需求（App / 小程序均必须满足）**：① 支持播放原视频（链接视频 + 上传视频）；② 用户可查看**完整文案**；③ **任选一句**进入跟读（音频或视频片段）。三者缺一不可。

---

## 2. 客户端框架选型

| 方案 | 包体 | 性能 | 分享/后台/录音 | 代码复用 | 结论 |
|---|---|---|---|---|---|
| **Flutter** | 中（arm64 ~15–20MB） | 高 | 需平台通道，成熟 | Android/iOS 一套 | **推荐**：体验与包体平衡最好 |
| React Native | 中（~15–25MB） | 中高 | 插件成熟 | 一套 | 可选，需 JS 团队 |
| 原生 Kotlin + Swift | **最小**（~8–12MB） | 最高 | 原生最佳 | 两套代码 | 包体/体验最优但成本最高 |
| uni-app (App 端) | 中（~12–20MB） | 中 | 插件/HBuilderX | **可复用小程序代码** | 若三端统一优先选它 |

> **决策建议**
> - 只做 App、重体验 → **Flutter**（本文档默认）。
> - 已决定同时维护小程序 + App + H5，且想一套代码 → **uni-app（App 端）**，但分享扩展/后台能力需原生插件补齐。
> - 对包体极其敏感（<12MB）→ 原生双端。

---

## 3. 包体控制（App 关键约束）

目标：**Android arm64 APK ≤ 20MB，iOS ipa ≤ 30MB**。

| 手段 | 说明 |
|---|---|
| 分 ABI 打包 | `flutter build apk --split-per-abi`，主流只留 `arm64-v8a` |
| App Bundle | Android 用 `.aab`，商店按设备下发，天然瘦身 |
| iOS App Thinning | 资源目录 + On-Demand Resources，按需下载 |
| 不内置重库 | 不打包 ffmpeg / Whisper / 大模型；媒体处理全在服务端 |
| 图片/字体 | WebP、字体子集化、图标字体 |
| 代码裁剪 | R8/ProGuard（Android）、Tree Shaking、去除未用资源 |
| 资源按需 | 音频/视频切片走 CDN，首次使用再缓存，不随包 |
| 可选离线模型 | 若日后要端侧 ASR，用**下载式模型包**，不内置 |

---

## 4. 总体架构

```
┌─────────────────────────── 手机 App (Android / iOS) ───────────────────────────┐
│  UI 层 (Flutter Widget)                                                          │
│     首页/导入     句子列表      跟读详情      我的                                  │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  状态层 (Riverpod / Bloc)                                                        │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  领域层 (UseCase)   项目 / 句子 / 录音 / 下载 / 播放                                │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  数据层 (Repository)                                                             │
│     API Client  |  SQLite/Drift  |  文件缓存  |  上传/下载队列                     │
│  ─────────────────────────────────────────────────────────────────────────────  │
│  原生能力层 (Platform Channel / 插件)                                             │
│     录音·播放  |  后台任务  |  分享扩展·DeepLink  |  推送  |  权限  |  锁屏控制      │
└────────────────────────────────────┬────────────────────────────────────────────┘
                                     │ HTTPS / (可选)WebSocket / WebSocket 推送
┌────────────────────────────────────▼────────────────────────────────────────────┐
│                            后端服务 (与小程序版共用)                               │
│  接入层: Nginx / API Gateway  →  FastAPI(鉴权·任务·项目·句子·录音)                  │
│  异步层: Redis + Celery  →  媒体 Worker (yt-dlp / ffmpeg / ASR / 分句 / 切片)      │
│  存储层: MySQL 8.0  |  OSS/COS + CDN                                            │
│  第三方: 云 ASR  |  发音评测  |  APNs / FCM 推送                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 分层职责

- **UI 层**：页面与组件，只做展示与交互。
- **状态层**：页面状态、加载/错误、缓存状态（离线）。
- **领域层**：业务用例（导入链接、拉句子、录音上传、A/B 对比），不依赖具体实现。
- **数据层**：网络 + 本地库 + 文件缓存，统一出口 `Repository`。
- **原生能力层**：录音、播放、后台、分享扩展、推送、权限、锁屏控制。
- **后端**：与小程序版一致，新增推送与设备鉴权即可。

---

## 5. 核心链路

```
① 用户在抖音点"分享"→ 选择本 App（iOS Share Extension / Android ACTION_SEND）
   或：App 内粘贴链接 / 选择本地音视频文件
② App → POST /tasks {url} 或上传文件；后端建 Project(status=queued) 返回 taskId
③ App 展示进度：轮询 GET /tasks/{id}；完成可经 APNs/FCM 推送提醒
④ 后端 Worker：yt-dlp 解析 → 下载 → ffmpeg 抽 16k 音频 → 云 ASR(带时间戳)
⑤ Worker：分句 + 逐句音频切片 + 原视频转码(H.264/AAC) → 上传 OSS → Project(status=ready)
⑥ App 拉取句子列表 / 全文；按需把句子音频缓存到本地（支持离线跟读）
⑦ 用户可**播放整段原视频**、**查看全文**、**任选一句** → 详情页播放该句(视频 seek / 音频)
⑧ 用户录音（原生 Recorder）→ 本地即时回放 → 后台上传
⑨ （可选）上传后服务端发音评测，返回总分/逐词得分，前端高亮
⑩ A/B 对比：原句 ↔ 我的录音；支持循环、慢放、上一句/下一句
```

---

## 6. 模块详细设计

### 6.1 分享接入与导入（App 体验核心）

- **iOS**：`Share Extension`，在抖音/微信的分享面板出现"影跟读"，接收 URL/文本，写入 App Group 后由主 App 处理。
- **Android**：`ACTION_SEND` / `ACTION_VIEW` Intent Filter，接收文本/链接。
- **Deep Link / Universal Link**：网页/其他 App 唤起并带入链接。
- App 内同时保留"粘贴链接 + 本地文件选择"作为兜底。

> 相比小程序的"复制链接再粘贴"，分享直达是 App 最大的体验优势。

### 6.2 链接解析与下载（服务端为主）

- 复用服务端 `resolver` + `yt-dlp`（抖音专用解析器前置、B站等原生支持）。
- 视频号内容不支持，提示"请上传本地文件"。
- **支持视频播放**：原视频在服务端转码为统一 mp4（H.264/AAC），App 端**流式播放**（边下边播，不整包落盘），单句用 `seek(start→end)`。
- **原始视频必须保留**以支持随时回放；保留期可配（如 30 天，用户删除即删），到期降级为"仅音频跟读"。

### 6.3 音频提取 / ASR / 分句（服务端，与小程序版一致）

```
ffmpeg -i input.mp4 -vn -ac 1 -ar 16000 -f wav audio.wav   # 给 ASR
ffmpeg -i input.mp4 -vn -b:a 64k audio.mp3                # 播放
```

- ASR：MVP 用云 ASR（火山/腾讯/阿里/讯飞）带时间戳；量大切 faster-whisper。抽象 `ASRProvider`。
- 分句：标点切分 + 最大时长(15s)/最大字数(中 40 字、英 25 词) + 过短合并，保留 `start_ms/end_ms`。
- 切片：逐句生成 mp3 存 OSS。
- 视频：转码 H.264 + AAC mp4（或 HLS 分片），支持 Range/seek；写入 `projects.video_url`。

### 6.4 视频 / 音频播放

- 音频：`just_audio`（或 `AVPlayer` / `ExoPlayer`），支持精准 seek、变速（0.5x–1.5x）、循环；`audio_service` 提供锁屏/通知栏控制与后台播放。
- 视频：`video_player` + 原生播放器流式播放原视频，支持 `seek(start_ms)`、到 `end_ms` 暂停/循环。
- **单句播放**：视频 `seek(start_ms)` → 播到 `end_ms`；与音频共用时间轴，保证音画同步。
- 原声与录音各用独立播放器实例，便于 A/B 切换。

### 6.4.1 全文视图与任选句

- **全文页**：完整文案逐句展示，**任一句可点击** → 进入该句详情或直接定位播放。
- 播放时按时间高亮当前句并自动滚动；支持"连续跟读"逐句推进。
- 可切换"看视频 / 只听音频"模式；视频不可用时自动降级音频。

### 6.5 录音

- 插件 `record`（底层 AVAudioRecorder / MediaRecorder），输出 aac/mp3，16k 单声道。
- 权限：麦克风首次申请，拒绝引导系统设置。
- 录音状态机：`idle → recording → hasRecording`；可覆盖重录。
- 本地先存临时文件并立即回放（无需等上传完成），上传走队列，弱网自动重试。

### 6.6 本地存储与离线

- **SQLite / Drift**：缓存项目、句子元数据、录音记录。
- **文件缓存**：句子音频切片（LRU 管理，设容量上限）。
- **离线跟读**：已缓存的项目在无网时仍可播放原句 + 录音（录音本地保存，联网后补传）。
- **上传/下载队列**：持久化队列，断点续传、失败重试。

### 6.7 对比（第一版不做评分）

1. **A/B 播放（v1）**：原句 → 我的录音，顺序/单独/循环。
2. **波形对比（后续）**：`audio_waveforms` 或自绘双波形，直观看到节奏差异。
3. **发音评分（后续版本，暂不实现）**：如需，再接评测 API（讯飞/腾讯/Azure），并需将录音上传服务端。

> v1 不接评测 API、不展示评分；`recordings.score` 仅预留字段。

### 6.8 推送与通知

- 任务完成推送（APNs / FCM）：长任务处理完提醒用户。
- 学习提醒（P2，可关闭）。
- 后端存 `device_tokens`，按平台路由。

### 6.9 鉴权

- App 启动匿名设备登录 → 换 JWT（+ refresh token），可选绑定手机号/微信。
- 所有媒体 URL 用**签名 URL**，防盗链。

---

## 7. 数据模型

服务端（与小程序版一致）：

```sql
-- MySQL 8.0 / InnoDB / utf8mb4
users(id, openid, phone, nickname, created_at)
projects(id, user_id, source_url, source_type, title, cover_url,
         source_video_url,        -- 原视频（支持播放，必须保留）
         video_status,            -- none/processing/ready/expired
         video_expire_at,         -- 视频保留到期
         status, progress, error_msg, duration_ms, lang, created_at, updated_at)
segments(id, project_id, idx, text, start_ms, end_ms, audio_url, video_url, created_at)
recordings(id, segment_id, user_id, audio_url, duration_ms, score, score_detail_json, created_at)
device_tokens(id, user_id, platform, token, created_at)   -- 推送
```

App 本地（SQLite/Drift）：

```
projects_cache, segments_cache, recordings_local,
download_queue, upload_queue, playback_history
```

---

## 8. API 设计

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/device` | 设备登录 → JWT + refresh |
| POST | `/api/auth/refresh` | 刷新 token |
| POST | `/api/tasks` | 提交链接，返回 taskId |
| POST | `/api/tasks/upload` | 上传本地音视频创建任务 |
| GET | `/api/tasks/{id}` | 状态/进度 |
| POST | `/api/push/register` | 注册 device token |
| GET | `/api/projects` | 我的项目 |
| GET | `/api/projects/{id}` | 项目详情（含 `video_url` 播放地址） |
| GET | `/api/projects/{id}/transcript` | 完整文案 + 全部句子（全文视图） |
| GET | `/api/projects/{id}/segments` | 句子列表（含音频切片、`start/end`、视频 seek 信息） |
| GET | `/api/projects/{id}/video` | 原视频播放地址（签名 URL / HLS manifest） |
| GET | `/api/projects/{id}/manifest` | 离线包清单（全部切片 URL + 大小） |
| POST | `/api/segments/{id}/recordings` | 上传录音 |
| POST | `/api/segments/{id}/score` | 发音评测（**v1 不实现，预留**） |
| GET | `/api/recordings/{id}` | 录音详情/回放 URL |

---

## 9. 页面与交互

```
[首页] ──粘贴链接 / 选择文件 / 从"分享"进入
   │
   ▼
[解析中/下载中: 进度条] ──失败──▶ [失败提示: 重试 / 上传本地文件]
   │ 完成
   ▼
[句子列表页]
   ├─ 顶部: 原视频播放器(整段) + 播放时高亮当前句、自动滚动
   ├─ [全文视图]: 完整文案，任一句可点选
   └─ 点任意一句
        ▼
[跟读详情页]
   ├─ ▶ 播放原句（视频 seek start→end / 音频）
   ├─ ● 录音 → 停止 → 按钮变 ▶ 播放（可覆盖重录）
   ├─ A/B 对比 / 波形（v1 不评分）
   └─ 上一句 / 下一句 / 返回列表
```

跟读详情页布局：

```
┌─────────────────────────────┐
│  ← 返回       第 3/20 句      │
│                             │
│  [视频/音频片段区域]          │
│  "今天我们来学习影子跟读。"    │
│                             │
│  [▶ 原文播放]   [● 录音]      │
│                (录音后变 ▶)   │
│  ── 我的录音 ──               │
│  [▶ 我的录音]   时长: 4.1s    │
│                             │
│  [上一句]        [下一句]     │
└─────────────────────────────┘
```

---

## 10. 技术风险与对策

| 风险 | 影响 | 对策 |
|---|---|---|
| 视频号无法下载 | 核心输入不可用 | 不支持，引导本地文件上传 |
| 抖音反爬变动 | 解析失败 | 解析器可插拔 + 定期升级 yt-dlp + 降级上传 |
| 包体超限 | 下载转化低 | 分 ABI、.aab、不内置重库、资源 CDN |
| iOS 分享扩展限制 | 分享体验 | App Group 传参 + 超时兜底（先存链接） |
| 后台/权限差异 | 录音/播放中断 | 统一状态机 + 权限引导 + 后台播放配置 |
| 版权/平台条款 | 合规风险 | 仅限自有/授权内容，免责声明 |
| ASR 成本 | 费用上升 | 时长上限 + 规模切换自建 Whisper |
| 弱网/离线 | 上传失败 | 本地队列 + 断点续传 + 自动重试 |
| 存储成本（需保留视频） | 费用高 | 保留期可配 + 低频存储 + 到期降级为仅音频；用户删除即删 |
| 视频播放流量/卡顿 | 体验差 | HLS 分片 + CDN + 预加载 + 自适应码率 |
| 应用商店审核 | 上架周期 | 提前准备隐私政策、录音权限说明、内容合规 |

---

## 11. 部署架构

```
                ┌──────────────────────┐
                │  Android App / iOS App │
                └───────────┬──────────┘
                            │ HTTPS
                ┌───────────▼──────────┐
                │   Nginx / API 网关    │
                └───────────┬──────────┘
                            │
             ┌──────────────▼──────────────┐
             │      FastAPI (多实例)         │
             └───┬──────────┬──────────┬───┘
                 │          │          │
          ┌──────▼───┐ ┌────▼─────┐ ┌──▼──────────┐
          │MySQL 8.0 │ │  Redis   │ │ OSS / COS   │
          └──────────┘ └────┬─────┘ └──────▲──────┘
                            │              │
              ┌─────────────▼──────────────┴────────┐
              │         Celery Worker 池              │
              │  ├ 媒体 Worker (yt-dlp/ffmpeg)        │
              │  └ ASR Worker (可挂 GPU)              │
              └──────────────┬───────────────────────┘
                             │
                      ┌──────▼──────┐        ┌──────────────┐
                      │  CDN 分发    │        │ APNs / FCM   │
                      └─────────────┘        └──────────────┘
```

- **开发环境**：Docker Compose 起 `api / worker / redis / mysql / minio`。
- **生产环境**：API 多实例；Worker 按队列伸缩，ASR Worker 可 GPU；OSS + CDN；Prometheus + Sentry。
- **App 构建产物**：Android `.aab`（分 ABI）；iOS `.ipa`（App Thinning）。
- **仓库结构（monorepo）**：

```
ying-gen-du/
├── src/
│   ├── api/            # FastAPI 业务服务
│   ├── worker/         # Celery 任务 + 媒体处理
│   ├── common/         # 配置/共享常量
│   └── app/            # Flutter (Android/iOS)（后续）
├── tests/
├── infra/
│   ├── docker-compose.yml
│   └── nginx/
├── docs/
└── 需求/
```

---

## 12. 推荐技术栈汇总

| 层 | 选型 | 备选 |
|---|---|---|
| App 框架 | Flutter | uni-app / React Native / 原生双端 |
| 状态管理 | Riverpod | Bloc / Provider |
| 本地库 | Drift(SQLite) | Isar / Hive |
| 播放（音频） | just_audio + audio_service | 原生 AVPlayer / ExoPlayer |
| 播放（视频） | video_player | 原生 AVPlayer / ExoPlayer |
| 录音 | record | 原生 AVAudioRecorder / MediaRecorder |
| 波形 | audio_waveforms | 自绘 canvas |
| 推送 | FCM + APNs | 极光 / 个推 |
| 业务 API | Python FastAPI | NestJS |
| 异步任务 | Celery + Redis | BullMQ / RQ |
| 媒体处理 | yt-dlp + ffmpeg | —— |
| ASR | 云 ASR(带时间戳) | faster-whisper / WhisperX |
| 发音评测 | 讯飞/腾讯/Azure | —— |
| 数据库 | MySQL 8.0 | PostgreSQL |
| 对象存储 | OSS / COS + CDN | MinIO(开发) |
| 部署 | Docker Compose / K8s | —— |

---

## 13. 分阶段实施计划

### P0 · MVP（约 3–4 周）
- App 骨架：首页/句子列表/全文页/跟读详情 + 状态管理 + 网络层
- 分享接入（iOS Share Extension / Android Intent）+ 粘贴链接 + 本地文件
- 服务端：下载 → 抽音频 + 转码原视频 → 云 ASR → 分句 → 切片（复用小程序版后端）
- **原视频整段播放 + 播放高亮当前句**
- **全文视图：完整文案，任一句可点选**
- 单句视频 seek / 音频播放、录音、A/B 回放
- 任务进度轮询

### P1 · 体验增强（约 2–3 周）
- 本地缓存 + 离线跟读 + 上传队列
- 推送通知（任务完成）
- 波形对比、循环/慢放、锁屏控制、视频/音频模式切换

### P2 · 扩展
- 单句视频片段预生成（离线缓存）
- 多平台（B站/播客）
- 自建 Whisper 降本
- 学习打卡、进度追踪、社交分享
- 端侧 ASR 模型按需下载（可选）
- **发音评分（若后续需要，再接讯飞/腾讯/Azure）**

---

## 14. 待确认决策点

1. **App 框架**：Flutter（体验优先）还是 uni-app（与小程序复用代码优先）？
2. **"微信视频"范围**：普通转发视频文件 还是 视频号？（决定是否以上传为主）
3. ~~发音评分是否必须~~ → **已确认：第一版不做评分，只做 A/B 回放。**
4. **原视频保留期**：是否长期保留原视频以支持随时播放？（直接影响存储成本；需确认 30 天/永久/用户删除即删）
5. **离线能力优先级**：是否必须支持无网跟读？（影响本地缓存与同步设计）
6. **登录方式**：设备匿名 / 手机号 / 微信 SDK。
7. **包体目标**：是否严格要求 Android ≤ 20MB？若 ≤ 12MB 需考虑原生双端。
8. **合规边界**：是否只允许自有/授权内容、是否需要内容审核与隐私合规备案。
