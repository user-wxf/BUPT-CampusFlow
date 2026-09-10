# 邮智办——北邮校园事务智能办理助手

## 项目简介

邮智办是面向北京邮电大学学生的校园事务智能办理助手，目标是把分散在制度文件、办事说明、考试安排和结构化事务数据中的信息，整理成学生可以理解和执行的办理建议。用户可以用自然语言提出问题，例如缓考、转专业、奖助学金、勤工助学、毕业结业等场景，系统会结合用户画像和知识库检索结果返回个性化说明。

与普通校园办事门户不同，本项目不是让学生在多个页面中手动查找制度条款，而是通过“浏览器前端 → 业务后端 → AI/RAG 服务”的三层结构，将用户画像、Metadata Filtering、校园政策知识库、结构化数据和 DeepSeek 生成能力组合起来，形成可追溯的办理指导。精确地点、联系人、办公时间、考试安排等信息只在资料或结构化数据中存在时展示，不由模型自行编造。

## 核心功能

- 用户登录与身份认证：支持注册、登录、JWT 签发与 Bearer Token 自动携带，后端对用户接口进行鉴权。
- 用户画像：保存学院、年级、培养层次、校区和邮箱等信息，用于智能查询时的个性化过滤和邮件提醒。
- 校园事务自然语言查询：前端提交用户问题，业务后端调用 AI/RAG 服务生成回答、办理方案、来源和注意事项。
- Metadata Filtering 个性化过滤：AI/RAG 服务按 college、grade、education_level、campus 等元数据过滤适用 Chunk。
- RAG 知识库检索：基于 `airag/data/chunks/chunks.jsonl` 与本地 `airag/vector_db/chunks.json` 进行向量检索，异常时保留关键词检索兜底。
- DeepSeek / LLM 生成：AI/RAG 服务读取 `DEEPSEEK_API_KEY` 调用 DeepSeek；未配置或调用失败时按代码逻辑返回基于检索内容的兜底回答。
- 政策来源与依据追溯：查询结果返回来源文件名和页码；后端与 AI/RAG 服务保留来源详情查询接口，但当前前端主要展示来源文件名与页码。
- 结构化办理步骤：结果页按 AI 办理建议、办理方案、所需材料、办理步骤、已知办理信息、信息来源和注意事项展示。
- 一键加入待办：可将办理方案中的有效步骤批量写入当前用户 Todo。
- DDL / 截止时间：Todo 支持 `due_at` 截止时间、完成状态、到期状态展示和修改。
- 邮件提醒：后端定时检查即将到期的 Todo，按用户画像中的邮箱发送提醒；SMTP 支持 SSL、STARTTLS 和 none 三种模式。
- 查询历史：保存用户智能查询记录，支持列表查看、回看结果和删除。

## 技术栈

- 前端：Vue 3、Vite、Axios、原生 CSS。
- 业务后端：FastAPI、Pydantic、SQLAlchemy、PyJWT、SQLite、httpx。
- AI/RAG 服务：FastAPI、Pydantic、fastembed、NumPy、本地向量库 JSON、Metadata Filtering、RAG Context Builder、DeepSeek API。
- 数据库：SQLite，默认数据库地址由 `DATABASE_URL` 控制，代码默认值为 `sqlite:///./youzhiban.db`。
- Embedding：默认使用 `BAAI/bge-small-zh-v1.5`，由 `fastembed` 在构建向量库时使用。
- 邮件：Python `smtplib`，支持 `SMTP_SSL`、`SMTP + starttls()` 和无加密连接。

整体调用关系：

```text
浏览器前端（Vue / Vite）
  ↓ /api
业务后端 B（FastAPI / SQLite / JWT / Todo / History / Reminder）
  ↓ RAG_URL
AI/RAG 服务 C（检索 / Metadata Filtering / DeepSeek）
```

## 项目目录

```text
BUPT-CampusFlow/
├── README.md                         # 项目说明
├── .env.example                      # 环境变量模板，不保存真实密钥
├── frontend/                         # Vue 3 + Vite 前端
│   ├── package.json                  # 前端脚本和依赖
│   ├── vite.config.js                # Vite 配置，/api 代理到后端 8000
│   └── src/
│       ├── App.vue                   # 前端主页面和交互逻辑
│       ├── main.js                   # Vue 入口
│       └── api/client.js             # Axios API client 与 JWT 注入
├── backend/                          # FastAPI 业务后端
│   ├── requirements.txt              # 后端 Python 依赖
│   ├── README.md                     # B 模块说明
│   ├── VALIDATION.md                 # 后端验证记录
│   ├── tests/test_api.py             # 后端接口与邮件提醒测试
│   └── app/
│       ├── main.py                   # API 路由、启动生命周期和 Reminder 调度
│       ├── database.py               # SQLite / SQLAlchemy 数据模型
│       ├── schemas.py                # 请求与响应 Schema
│       ├── security.py               # 密码哈希、JWT、鉴权
│       ├── rag.py                    # B → C 调用边界
│       ├── reminders.py              # Todo DDL 邮件提醒逻辑
│       └── email_service.py          # SMTP 邮件发送
├── airag/                            # AI/RAG 服务、知识库和向量库
    ├── requirements.txt              # AI/RAG Python 依赖
    ├── app.py                        # C 服务 FastAPI 入口
    ├── retrieval.py                  # Chunk 加载、过滤、检索和来源证据查询
    ├── embedding.py                  # Embedding 封装
    ├── vector_store.py               # 本地向量库构建与查询
    ├── context_builder.py            # RAG 上下文构建
    ├── prompt.py                     # DeepSeek Prompt 约束
    ├── llm.py                        # DeepSeek API 调用
    ├── scripts/                      # 知识库导入和向量库构建脚本
    ├── data/                         # raw、processed、metadata、chunks 数据
    └── vector_db/                    # 本地向量库文件

```

## 环境要求

- Python：项目未固定精确版本，建议使用 Python 3.11 或兼容依赖的 Python 3.x。
- Node.js：用于运行 Vite 前端，建议使用当前 LTS 版本。
- pnpm：前端仓库包含 `pnpm-lock.yaml`，推荐使用 pnpm 安装依赖。
- 网络：首次安装依赖、首次下载 fastembed 模型、调用 DeepSeek API 时需要联网。
- DeepSeek API Key：真实智能回答需要配置 `DEEPSEEK_API_KEY`。
- SMTP 邮箱授权码：使用邮件提醒需要配置 SMTP 主机、端口、用户名、授权码或密码。
- 部署方式：当前项目主要按本地三服务方式运行。

## 安装与启动

以下命令以 Windows PowerShell 为主。

1. 克隆并进入项目：

```powershell
git clone <your-repository-url>
cd BUPT-CampusFlow
```

2. 创建并启用 Python 虚拟环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

3. 安装后端与 AI/RAG 依赖：

```powershell
python -m pip install -r backend\requirements.txt
python -m pip install -r airag\requirements.txt
```

4. 安装前端依赖：

```powershell
cd frontend
pnpm install
cd ..
```

5. 配置环境变量：

```powershell
Copy-Item .env.example .env
```

然后编辑根目录 `.env`，按本机环境填写真实值。至少需要关注：

```env
DEEPSEEK_API_KEY=your_api_key_here
JWT_SECRET_KEY=please_use_a_long_random_secret_at_least_32_chars
RAG_MODE=http
RAG_URL=http://127.0.0.1:8001/generate
```

如果只想验证后端基础接口，也可以使用代码默认的 `RAG_MODE=demo`，但该模式不会调用真实 RAG 和 DeepSeek。

后端会在启动时读取根目录 `.env`。AI/RAG 服务使用进程环境变量；如需让 C 服务调用 DeepSeek，请确保启动 C 服务的终端中也能读取到 `DEEPSEEK_API_KEY`，例如在 PowerShell 中设置：

```powershell
$env:DEEPSEEK_API_KEY="your_api_key_here"
```

6. 构建或重建向量数据库：

如果 `airag/vector_db/chunks.json` 不存在，或修改了 `airag/data/chunks/chunks.jsonl`，需要重新构建向量库：

```powershell
python -m airag.scripts.build_vector_db
```

该命令会读取 `airag/data/chunks/chunks.jsonl`，生成 `airag/vector_db/chunks.json`。

7. 启动 AI/RAG 服务：

```powershell
python -m uvicorn airag.app:app --host 0.0.0.0 --port 8001
```

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

8. 启动业务后端：

另开一个 PowerShell 窗口(确保在根目录)：

```powershell
cd backend
..\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

上面激活虚拟环境命令中的路径请按实际项目位置调整；如果已经处于启用状态，可直接启动 uvicorn。

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

9. 启动前端：

另开一个 PowerShell 窗口(确保在根目录)：

```powershell
cd frontend
pnpm run dev --host 0.0.0.0 --port 5300
```

浏览器本机访问：

```text
http://127.0.0.1:5300/
```

`frontend/vite.config.js` 会将前端的 `/api` 请求代理到 `http://127.0.0.1:8000`。如果端口被占用，可以换用其他空闲前端端口。同一局域网中可使用运行主机 IPv4 访问，能否互通取决于网络策略和防火墙设置。

10. 前端构建检查：

```powershell
cd frontend
pnpm run build
```


## 核心接口

前端通常通过 `/api` 访问业务后端，Vite 开发环境会把 `/api` 代理到后端服务。

| 接口 | 方法 | 作用 |
| --- | --- | --- |
| `/api/health` | GET | 后端健康检查，返回服务状态与 RAG 模式 |
| `/api/auth/register` | POST | 用户注册 |
| `/api/auth/login` | POST | 用户登录并返回 JWT |
| `/api/auth/me` | GET | 获取当前登录用户 |
| `/api/profile` | GET / PUT / DELETE | 获取、保存、删除用户画像 |
| `/api/query` | POST | 提交自然语言事务问题，调用 B → C 查询链路 |
| `/api/todos` | GET / POST | 查询和新增 Todo |
| `/api/todos/{item_id}` | GET / PUT / DELETE | 查看、更新、删除单条 Todo |
| `/api/reminders/check` | POST | 手动触发当前用户 Todo DDL 邮件提醒检查 |
| `/api/history` | GET | 查询历史列表 |
| `/api/history/{item_id}` | GET / DELETE | 回看或删除单条历史记录 |
| `/api/affairs` | GET | 查询结构化事务数据 |
| `/api/admin/affairs` | POST | 管理员新增事务 |
| `/api/admin/affairs/{item_id}` | PUT / DELETE | 管理员更新或删除事务 |
| `/api/admin/logs` | GET | 管理员查看事务操作审计 |
| `/api/sources/evidence` | GET | 来源详情查询接口，当前前端主要展示来源文件名与页码 |

AI/RAG 服务主要接口：

| 接口 | 方法 | 作用 |
| --- | --- | --- |
| `/health` | GET | C 服务健康检查、Chunk 数和向量库状态 |
| `/generate` | POST | 根据问题、画像和结构化事务数据生成 RAG 查询结果 |
| `/sources/evidence` | GET | 按来源标题和页码查询命中的 Chunk 依据 |

## 配置与密钥说明

`.env.example` 只保存模板；真实密钥应通过本机环境变量或未纳入 Git 的 `.env` 配置；不得将真实 API Key、邮箱授权码、SMTP 密码、个人邮箱密码或 JWT Secret 提交到 GitHub。

| 变量 | 用途 |
| --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API Key，真实 RAG 回答需要配置 |
| `DEEPSEEK_MODEL` | DeepSeek 模型名，代码默认 `deepseek-chat` |
| `JWT_SECRET_KEY` | JWT 签名密钥，后端要求长度至少 32 位 |
| `DATABASE_URL` | SQLite 数据库地址，未配置时使用代码默认值 |
| `RAG_MODE` | 后端 RAG 模式，`demo` 为演示模式，`http` 为调用 C 服务 |
| `RAG_URL` | C 服务 `/generate` 地址，例如 `http://127.0.0.1:8001/generate` |
| `RAG_API_KEY` | B 与 C 之间可选的 Bearer 密钥 |
| `RAG_VECTOR_DB_PATH` | C 服务本地向量库路径，未配置时使用默认路径 |
| `CORS_ORIGINS` | 后端允许的跨域来源列表 |
| `SMTP_HOST` | SMTP 服务器地址，例如 `smtp.example.com` |
| `SMTP_PORT` | SMTP 端口，例如 STARTTLS 常见 `587`，SSL 常见 `465` |
| `SMTP_USERNAME` | SMTP 用户名 |
| `SMTP_PASSWORD` | SMTP 授权码或密码 |
| `SMTP_FROM` | 邮件发件人地址，未配置时使用 `SMTP_USERNAME` |
| `SMTP_SECURITY` | SMTP 加密模式，允许 `ssl`、`starttls`、`none` |
| `SMTP_USE_TLS` | 兼容旧配置的 TLS 开关，优先级低于 `SMTP_SECURITY` |
| `REMINDER_CHECK_INTERVAL_MINUTES` | 后端自动扫描 Todo DDL 的间隔分钟数 |
| `REMINDER_LEAD_HOURS` | Todo 到期前多少小时触发提醒 |
| `REMINDER_SCHEDULER_ENABLED` | 是否启用后端 Reminder 定时任务 |

163 邮箱常见配置示例：

```env
SMTP_HOST=smtp.163.com
SMTP_PORT=465
SMTP_SECURITY=ssl
SMTP_USERNAME=your_163_email@example.com
SMTP_PASSWORD=your_smtp_authorization_code
SMTP_FROM=your_163_email@example.com
```

## 常见问题

1. 前端页面打不开

确认前端依赖已安装，并使用了空闲端口启动：

```powershell
cd frontend
pnpm install
pnpm run dev --host 0.0.0.0 --port 5300
```

2. 前端能打开但接口请求失败

确认业务后端运行在 `http://127.0.0.1:8000`，并检查 `frontend/vite.config.js` 中 `/api` 代理目标是否与后端地址一致。

3. 智能查询提示 RAG 服务异常

确认 `.env` 中设置了 `RAG_MODE=http` 和正确的 `RAG_URL`，并确认 C 服务已启动：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
```

4. `vector_db` 未生成或知识库修改后检索结果没有更新

重新构建向量库：

```powershell
python -m airag.scripts.build_vector_db
```

5. DeepSeek 无法生成真实回答

检查 `DEEPSEEK_API_KEY` 是否已在本机 `.env` 中配置，且当前环境可以访问 DeepSeek API。未配置或调用失败时，C 服务会按代码逻辑返回检索兜底回答。

6. SMTP 邮件提醒发送失败

检查用户画像中是否填写邮箱，Todo 是否设置了未来截止时间，并确认 SMTP 配置、授权码、端口和 `SMTP_SECURITY` 是否匹配邮箱服务商要求。

## 已知限制

- 当前项目主要采用本地部署，未从代码中确认公网部署配置。
- `localhost` / `127.0.0.1` 只能用于本机访问；局域网访问依赖运行主机持续在线、端口开放、网络互通和防火墙策略。
- SQLite 当前属于本地数据库，适合课程项目和本地演示，不等同于生产级多实例数据库。
- AI 回答依赖当前 `airag/data` 知识库覆盖范围；知识库缺失时不能保证回答完整。
- 精确考试时间、地点、房间、联系人、办公时间等信息只有在结构化数据或知识库中真实存在时才能展示。
- 修改知识库 Chunk 后必须重建向量库，否则向量检索不会自动更新。
- 邮件提醒依赖正确 SMTP 配置、用户画像邮箱、Todo 截止时间和持续运行中的后端服务。
- 当前查询流程以单轮自然语言查询为主，未从代码中确认真正的多轮对话状态管理。
- 部分数据导入脚本处理 PDF、Word、Excel 等文件时可能需要本机具备对应解析依赖或运行环境，具体以脚本报错和实际环境为准。