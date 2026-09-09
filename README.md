# 邮智办 - 北邮校园事务智能办理助手

英文内部项目名：**BUPT CampusFlow**

本仓库用于课程项目“邮智办 - 北邮校园事务智能办理助手”的协作开发。README 不只是项目介绍，也作为三人小组的项目说明、技术架构说明、成员任务说明、GitHub 协作规范和本地开发指南。

第一次加入项目的组员，应优先阅读本文，明确：

- 项目要解决什么问题；
- 系统整体技术架构是什么；
- 自己主要负责哪些模块；
- 自己应该修改哪些目录；
- 哪些目录不要随便修改；
- 三个人之间如何通过接口协作；
- 项目如何在本地启动；
- GitHub 代码如何拉取、开发、提交、合并；
- 多人协作时如何避免代码冲突；
- 每天开始和结束开发时分别应该做什么。

> 说明：本文描述的是当前课程项目的设计和协作约定。若代码尚未完全实现，相关内容均表示计划或预期方式，最终以实际代码和 `docs/` 下文档为准。

---

## 一、项目背景

**项目名称：** 邮智办 - 北邮校园事务智能办理助手

**项目定位：** 面向北京邮电大学学生的校园事务智能办理助手。

本系统不是简单的大模型聊天机器人，而是希望将学校官网、学院通知、制度文件、办事指南以及结构化事务数据，转化成符合学生个人身份的可执行办理方案。

系统主要结合：

- 用户画像
- 结构化事务数据库
- RAG 知识库
- Metadata Filtering
- Context Builder
- DeepSeek API
- 待办管理

用户输入自然语言事务需求后，系统根据学院、年级、培养层次、校区等用户画像筛选适用资料，并最终生成：

- 办理条件
- 材料清单
- 办理流程
- 地点
- 负责人
- 办公时间
- 注意事项
- 信息来源
- 可加入个人待办的办理步骤

需要特别注意：

- RAG 主要处理学校制度、通知、办事指南等非结构化长文本。
- SQLite 结构化数据库主要保存用户、用户画像、事务、地点、房间、负责人、办公时间、联系方式、待办、查询记录、权限、管理员操作记录等结构化数据。
- 大模型不得自行生成地点、老师姓名、联系方式、办公时间等高精度信息。这类信息应优先来自结构化数据库或可追溯来源。

---

## 二、整体技术架构

当前设计采用 B/S 架构。浏览器访问 Vue 3 + Vite 前端，前端通过 HTTP + JSON 调用 FastAPI 后端。后端负责认证、权限、业务数据、查询流程编排，并在智能查询场景中调用 RAG 模块和 DeepSeek API，最终将结构化办理方案返回前端展示。

```text
浏览器
│
▼
Vue 3 + Vite
学生端 / 管理员端
│
│ HTTP + JSON
▼
FastAPI
│
├── 登录认证
├── 权限管理
├── 用户画像
├── 事务业务逻辑
├── 待办管理
└── 查询流程编排
     │
     ├───────────────┐
     ▼               ▼
SQLite             RAG模块
结构化数据           │
                     ├ 文档解析
                     ├ Chunk
                     ├ Embedding
                     ├ Vector DB
                     └ Metadata Filtering
     │               │
     └───────┬───────┘
             ▼
       Context Builder
             │
             ▼
        DeepSeek API
             │
             ▼
       结构化办理方案
             │
             ▼
         FastAPI
             │
             ▼
          Vue展示
```

各层说明：

| 层级 | 当前设计职责 |
| --- | --- |
| 浏览器 | 学生和管理员通过浏览器使用系统。 |
| Vue 3 + Vite | 负责学生端、管理员端页面展示、表单输入、交互状态和 API 调用。 |
| FastAPI | 负责后端接口、认证鉴权、权限管理、业务流程编排和统一响应。 |
| SQLite | 保存用户、画像、事务、待办、查询记录、管理员日志等结构化业务数据。 |
| RAG 模块 | 处理制度、通知、办事指南等非结构化资料，完成解析、切片、向量化、检索和过滤。 |
| Context Builder | 将用户画像、结构化数据和 RAG 检索结果组合为大模型可使用的上下文。 |
| DeepSeek API | 根据上下文生成结构化办理方案，不负责凭空生成高精度事务信息。 |
| Vue 展示 | 将后端返回的办理条件、材料清单、流程、地点、来源等内容展示给用户。 |

### 技术栈

| 模块 | 技术 |
| --- | --- |
| 前端 | Vue 3、Vite、Vue Router、Axios、HTML、CSS、JavaScript |
| 后端 | Python、FastAPI、Pydantic、SQLAlchemy、SQLite、JWT |
| AI / RAG | Python、PDF / Word 文本解析、Chunk、Embedding、Vector Database、Metadata Filtering、Query Rewrite、Context Engineering / Context Builder、DeepSeek API、JSON 结构化输出 |
| 测试 | FastAPI Swagger、pytest、必要时 Postman |
| 版本控制 | Git、GitHub |

---

## 三、项目目录结构

当前计划的根目录结构如下。实际开发中如需新增目录，应先确认是否符合三人分工边界，并同步到 README 或 `docs/` 文档中。

```text
bupt-campusflow/
│
├── README.md
├── .gitignore
├── .env.example
├── requirements.txt
│
├── frontend/
│   ├── index.html
│   ├── package.json
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   │   └── index.js
│   │   ├── api/
│   │   │   ├── auth.js
│   │   │   ├── profile.js
│   │   │   ├── query.js
│   │   │   ├── todo.js
│   │   │   └── admin.js
│   │   ├── views/
│   │   │   ├── Login.vue
│   │   │   ├── Home.vue
│   │   │   ├── Profile.vue
│   │   │   ├── Query.vue
│   │   │   ├── Result.vue
│   │   │   ├── Todo.vue
│   │   │   ├── History.vue
│   │   │   └── Admin.vue
│   │   ├── components/
│   │   │   ├── ServiceCard.vue
│   │   │   ├── MaterialList.vue
│   │   │   ├── ProcessSteps.vue
│   │   │   ├── SourceList.vue
│   │   │   └── EmptyState.vue
│   │   └── assets/
│   └── public/
│
├── backend/
│   ├── main.py
│   └── app/
│       ├── __init__.py
│       ├── api/
│       │   ├── auth.py
│       │   ├── profile.py
│       │   ├── query.py
│       │   ├── todo.py
│       │   └── admin.py
│       ├── models/
│       │   ├── user.py
│       │   ├── profile.py
│       │   ├── service.py
│       │   ├── todo.py
│       │   └── log.py
│       ├── schemas/
│       │   ├── auth.py
│       │   ├── profile.py
│       │   ├── query.py
│       │   └── todo.py
│       ├── services/
│       │   ├── auth_service.py
│       │   ├── query_service.py
│       │   ├── todo_service.py
│       │   └── ai_service.py
│       ├── core/
│       │   ├── config.py
│       │   ├── security.py
│       │   └── database.py
│       └── db/
│
├── ai_rag/
│   ├── __init__.py
│   ├── ingestion/
│   │   ├── document_loader.py
│   │   ├── cleaner.py
│   │   └── chunker.py
│   ├── retrieval/
│   │   ├── embedding.py
│   │   ├── vector_store.py
│   │   ├── metadata_filter.py
│   │   └── retriever.py
│   ├── llm/
│   │   ├── deepseek_client.py
│   │   ├── prompts.py
│   │   └── output_parser.py
│   ├── pipeline/
│   │   ├── intent.py
│   │   ├── context_builder.py
│   │   ├── validator.py
│   │   └── query_pipeline.py
│   └── vector_db/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── demo/
│
├── tests/
│   ├── backend/
│   ├── rag/
│   └── integration/
│
├── docs/
│   ├── architecture.md
│   ├── api-contract.md
│   ├── database-design.md
│   ├── rag-design.md
│   └── team-workflow.md
│
└── scripts/
    ├── init_db.py
    └── build_vector_db.py
```

目录说明：

| 目录或文件 | 作用 | 主要维护成员 |
| --- | --- | --- |
| `README.md` | 项目总说明、协作规范、本地启动指南。 | 三人共同维护 |
| `.gitignore` | 规定不提交到 GitHub 的文件，如 `.env`、虚拟环境、数据库文件、构建产物等。 | 三人共同维护 |
| `.env.example` | 环境变量示例文件，可提交到 GitHub，不包含真实密钥。 | 成员B为主，成员C协助 DeepSeek 配置 |
| `requirements.txt` | Python 依赖列表，供后端和 AI/RAG 模块安装使用。 | 成员B、成员C |
| `frontend/` | 前端工程目录，包含 Vue 页面、路由、组件和 API 调用封装。 | 成员A |
| `frontend/src/api/` | 前端对后端接口的调用封装，如登录、画像、查询、待办、管理员接口。 | 成员A，与成员B联调 |
| `frontend/src/views/` | 页面级组件，如登录、首页、画像、查询、结果、待办、历史、管理员页面。 | 成员A |
| `frontend/src/components/` | 可复用 UI 组件，如材料清单、流程步骤、信息来源、空状态等。 | 成员A |
| `backend/` | FastAPI 后端工程目录，负责接口、认证、权限、业务逻辑和系统调度。 | 成员B |
| `backend/app/api/` | 后端路由接口层，按功能拆分认证、画像、查询、待办、管理员接口。 | 成员B |
| `backend/app/models/` | SQLAlchemy 数据库模型。 | 成员B |
| `backend/app/schemas/` | Pydantic 请求和响应数据模型。 | 成员B，与成员A确认接口字段 |
| `backend/app/services/` | 业务逻辑层，组织认证、查询、待办、AI/RAG 调用等流程。 | 成员B |
| `backend/app/core/` | 配置、安全、数据库连接等核心基础代码。 | 成员B |
| `backend/app/db/` | 本地 SQLite 数据库文件或数据库相关资源目录。数据库文件通常不直接提交。 | 成员B |
| `ai_rag/` | AI/RAG 模块目录，负责资料解析、向量检索、上下文构建和大模型调用。 | 成员C |
| `ai_rag/ingestion/` | 文档加载、文本清洗、Chunk 切片流程。 | 成员C |
| `ai_rag/retrieval/` | Embedding、Vector DB、Metadata Filtering、语义检索。 | 成员C |
| `ai_rag/llm/` | DeepSeek API 调用、Prompt 模板、结构化输出解析。 | 成员C |
| `ai_rag/pipeline/` | 意图识别、Context Builder、结果校验、完整查询链路。 | 成员C，与成员B联调 |
| `ai_rag/vector_db/` | 本地生成的向量数据库目录。通常不作为主要 Git 协作对象。 | 成员C |
| `data/raw/` | 原始制度、通知、办事指南资料。 | 成员C |
| `data/processed/` | 清洗后、切片前后可复用的数据。 | 成员C |
| `data/demo/` | 可重复生成数据库或演示流程的 Demo 数据。 | 三人共同维护 |
| `tests/backend/` | 后端接口和业务逻辑测试。 | 成员B |
| `tests/rag/` | RAG 检索、过滤、输出结构测试。 | 成员C |
| `tests/integration/` | 前后端、后端与 RAG 的整体联调测试。 | 三人共同维护 |
| `docs/` | 架构、接口、数据库、RAG、团队流程等补充文档。 | 三人共同维护 |
| `scripts/init_db.py` | 初始化 SQLite 数据库。 | 成员B |
| `scripts/build_vector_db.py` | 构建本地向量数据库。 | 成员C |

---

## 四、三人技术分工

### 成员A：前端交互与用户体验

成员A主要负责 `frontend/`。目标是实现学生端和管理员端的浏览器页面，让用户能够完成登录、填写画像、发起事务查询、查看办理结果、管理待办和查看历史记录。

主要任务：

- Vue 3 项目搭建
- Vite 工程配置
- 页面布局
- 登录注册页面
- 用户画像页面
- 首页
- 智能事务查询页面
- 办理结果展示
- 材料清单展示
- 办理步骤展示
- 信息来源展示
- 个人待办页面
- 查询历史页面
- 管理员端页面
- 页面加载状态
- 空状态
- 错误状态
- Axios 调用 FastAPI 接口
- A 与 B 前后端联调

成员A原则：

- 前端只负责输入、展示、交互和 API 调用。
- 不要在 Vue 中写学院规则判断、年级规则判断、校区规则判断、权限核心逻辑或 RAG 逻辑。
- 所有业务规则和权限判断应由后端处理，前端根据后端返回结果展示。
- 接口字段以 `docs/api-contract.md` 为准，不根据自己的理解随意增删字段。

成员A主要修改：

- `frontend/`
- 必要时参与修改 `docs/api-contract.md`
- 必要时参与修改 `tests/integration/`

---

### 成员B：后端业务与系统工程

成员B主要负责 `backend/` 和 `scripts/init_db.py`。目标是搭建 FastAPI 后端、设计 SQLite 结构化数据库、完成认证权限和业务接口，并负责系统总调度。

主要任务：

- FastAPI 工程
- API 设计
- Pydantic 数据模型
- SQLite 数据库
- SQLAlchemy
- 用户注册登录
- JWT
- 学生/管理员权限
- 用户画像 CRUD
- 事务数据 CRUD
- 待办 CRUD
- 查询历史
- 管理员日志
- 结构化事务信息
- `/api/query` 核心接口
- 后端异常处理
- 系统总调度

成员B负责的 SQLite 结构化数据：

- 用户
- 用户画像
- 事务
- 地点
- 房间
- 负责人
- 办公时间
- 联系方式
- 待办
- 查询记录
- 权限
- 管理日志

成员B原则：

- B 不重新实现 RAG。
- B 通过明确的 Python 模块函数接口调用成员C提供的 AI/RAG 模块。
- B 负责 `/api/query` 的接口入口、用户身份识别、权限校验、画像读取、结构化数据读取、RAG 调用编排和统一返回。
- 数据库结构变化后，应更新 `docs/database-design.md`。
- 接口字段变化前，应先同步成员A，并更新 `docs/api-contract.md`。

成员B主要修改：

- `backend/`
- `scripts/init_db.py`
- `docs/api-contract.md`
- `docs/database-design.md`
- `tests/backend/`
- 必要时参与修改 `tests/integration/`

---

### 成员C：AI、RAG 与个性化检索

成员C主要负责 `ai_rag/`、`data/` 和 `scripts/build_vector_db.py`。目标是整理北邮制度、通知、办事指南等资料，构建可检索的知识库，并为后端提供可调用的 AI/RAG 能力模块。

主要任务：

- 北邮官方制度资料整理
- PDF / Word 解析
- 文本清洗
- Chunk
- Metadata
- Embedding
- Vector DB
- Metadata Filtering
- 语义检索
- 事务意图识别
- Query Rewrite
- Context Builder
- Prompt
- DeepSeek API
- JSON 结构化输出
- 来源追溯
- Validator
- RAG 测试

Metadata 至少考虑：

- `service`
- `college`
- `degree`
- `grade`
- `campus`
- `source`
- `updated_at`
- `status`

成员C原则：

- C 不负责用户登录、权限、待办、普通业务数据库 CRUD。
- 用户身份、权限、待办、查询记录等由成员B在后端统一处理。
- C 负责向量知识库，不维护 SQLite 结构化业务数据库中的同类信息。
- C 提供模块函数给 B 调用，不绕过后端直接与前端交互。
- RAG 结构变化后，应更新 `docs/rag-design.md`。

成员C主要修改：

- `ai_rag/`
- `data/`
- `scripts/build_vector_db.py`
- `docs/rag-design.md`
- `tests/rag/`
- 必要时参与修改 `tests/integration/`

---

## 五、三人接口边界

### A 与 B：前后端 HTTP API 协作

A 与 B 通过 HTTP API 协作。接口定义统一写在：

```text
docs/api-contract.md
```

协作规则：

- A 根据 `docs/api-contract.md` 调用接口和展示数据。
- A 不能根据自己的理解随意修改请求字段或响应字段。
- B 修改 API 字段前必须同步 A。
- B 修改 API 字段后必须更新 `docs/api-contract.md`。
- 前端不重复实现后端业务规则，不在页面里硬编码学院、年级、校区等判断。

### B 与 C：Python 模块函数接口协作

B 与 C 通过 Python 模块函数接口协作。C 至少需要提供类似能力：

```python
recognize_intent(question)

search_knowledge(
    question,
    profile,
    service
)

build_context(
    profile,
    structured_data,
    rag_result
)

generate_answer(context)

validate_answer(...)
```

协作规则：

- B 调用这些函数完成 `/api/query`。
- B 负责读取登录用户画像，不要求前端重复传学院、年级、校区等画像字段。
- B 负责读取 SQLite 中的结构化事务数据。
- C 负责语义检索、Metadata Filtering、Context Builder、Prompt 和 DeepSeek API 调用。
- C 的输出应尽量稳定为结构化 JSON，方便 B 统一封装并返回给前端。

### 数据库边界

B 负责 SQLite 结构化数据库。

C 负责向量知识库。

不要把同一类信息在两个数据库中重复维护。例如：

- 地点、房间、负责人、联系方式、办公时间等高精度事务信息，优先放入 SQLite 结构化数据库。
- 制度原文、通知原文、办事指南长文本、Chunk、Embedding、Metadata 检索索引，放入 RAG 知识库。

---

## 六、核心 API 约定

以下是 `/api/query` 的初步接口约定，用于三人对齐方向。最终字段以 `docs/api-contract.md` 为准。

### POST `/api/query`

用户登录后，前端主要发送：

```json
{
  "question": "我想申请缓考"
}
```

说明：

- 用户画像由后端根据登录用户从 SQLite 读取。
- 不要要求前端每次重复发送学院、年级、校区等数据。
- 后端应根据登录状态识别用户身份，并结合用户画像完成个性化查询。

后端建议统一返回：

```json
{
  "success": true,
  "data": {
    "service": "缓考申请",
    "applicable_to": {},
    "conditions": [],
    "materials": [],
    "steps": [],
    "location": {},
    "contact": {},
    "notes": [],
    "sources": []
  }
}
```

字段含义：

| 字段 | 含义 |
| --- | --- |
| `success` | 请求是否成功。 |
| `data.service` | 识别出的事务名称，如“缓考申请”。 |
| `data.applicable_to` | 适用对象信息，如学院、年级、培养层次、校区等。 |
| `data.conditions` | 办理条件。 |
| `data.materials` | 材料清单。 |
| `data.steps` | 办理流程，可用于生成待办步骤。 |
| `data.location` | 办理地点、房间等信息。 |
| `data.contact` | 负责人、联系方式等信息。 |
| `data.notes` | 注意事项。 |
| `data.sources` | 信息来源，用于追溯回答依据。 |

---

## 七、GitHub 协作策略

本项目采用：

```text
一个 GitHub 仓库 + 多 Feature Branch
```

禁止三个人分别维护三个独立仓库。所有成员都围绕同一个 GitHub 仓库协作。

主分支：

```text
main
```

要求：

- `main` 始终保持可以运行或至少处于可集成状态。
- 原则上不要直接在 `main` 上开发功能。
- 每次开发新功能，都从 `main` 创建 Feature Branch。
- 功能完成后，通过 Pull Request 合并回 `main`。

Feature Branch 命名示例：

```text
feature/frontend-login
feature/frontend-profile
feature/frontend-query

feature/backend-auth
feature/backend-profile
feature/backend-query
feature/backend-todo

feature/rag-ingestion
feature/rag-retrieval
feature/rag-metadata
feature/rag-llm
```

Bug 修复分支：

```text
fix/login-token-expired
fix/query-empty-result
```

文档分支：

```text
docs/api-contract
docs/readme-update
```

---

## 八、每日标准 Git 工作流程

### 每天开始写代码之前

先切回 `main`，拉取最新代码：

```bash
git checkout main
git pull origin main
```

如果今天要创建新功能分支：

```bash
git checkout -b feature/xxx
```

如果功能分支已经存在：

```bash
git checkout feature/xxx
```

然后把最新 `main` 合并到自己的功能分支：

```bash
git merge main
```

为什么需要先同步 `main`：

- 其他成员可能已经合并了新接口、新数据库结构或新页面。
- 先同步可以尽早发现冲突，避免自己写一天代码后才发现基础文件已经变了。
- 让自己的功能分支基于最新版本开发，更容易通过 Pull Request。

### 开发过程中

随时查看当前修改：

```bash
git status
```

完成一个相对独立的小功能后提交：

```bash
git add .
git commit -m "feat: add student profile page"
```

建议：

- 不要一天只提交一次巨大 commit。
- 一个 commit 尽量只做一类明确修改。
- 提交前先看 `git status`，避免把无关文件提交进去。

### 提交到 GitHub

```bash
git push origin feature/xxx
```

然后通过 GitHub：

```text
Feature Branch
→ Pull Request
→ main
```

禁止未经确认直接强制覆盖 `main`。

---

## 九、Commit 规范

采用简单 Conventional Commit 风格：

| 类型 | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复 Bug |
| `docs` | 文档 |
| `style` | 页面样式 |
| `refactor` | 重构 |
| `test` | 测试 |
| `chore` | 配置或杂项 |

示例：

```bash
git commit -m "feat: add student login page"
git commit -m "feat: implement JWT authentication"
git commit -m "feat: implement metadata filtering"
git commit -m "feat: add RAG retrieval pipeline"
git commit -m "fix: handle empty RAG result"
git commit -m "fix: resolve login token issue"
git commit -m "docs: update API contract"
git commit -m "style: improve query result layout"
```

一个 commit 尽量对应一个相对明确的修改。

不要使用以下无法说明内容的 commit message：

```text
update
change
修改一下
111
final
final2
真的final
```

---

## 十、Pull Request 规范

完成一个功能后：

1. Push 自己的 Feature Branch。
2. 打开 GitHub。
3. 创建 Pull Request。
4. PR 目标分支选择 `main`。
5. 简单说明做了什么、修改了哪些模块、如何测试、是否影响其他成员接口。

PR 示例：

```text
Title:
feat: implement student profile API

Description:
- 新增用户画像 CRUD 接口
- 新增 Profile Pydantic Schema
- 新增 SQLAlchemy Profile Model
- 已通过 Swagger 测试
- 前端可以开始调用 /api/profile
```

建议至少由另一名成员简单检查后再 Merge。

PR 描述建议包含：

| 项目 | 说明 |
| --- | --- |
| 做了什么 | 简要说明新增或修改的功能。 |
| 修改了哪些模块 | 例如 `frontend/`、`backend/app/api/`、`ai_rag/retrieval/`。 |
| 如何测试 | 说明运行了哪些命令，或用 Swagger / 页面手动验证了哪些流程。 |
| 是否影响接口 | 如果影响 A/B/C 对接字段，必须明确写出。 |
| 是否更新文档 | 如果接口、数据库或 RAG 结构变化，应说明已更新对应文档。 |

---

## 十一、冲突处理原则

这一部分特别写给 Git 新手。

如果发现：

- A 和 B 同时修改同一个文件；
- B 和 C 同时修改 `query_service.py`；
- 自己 `git merge main` 后出现 Conflict；

不要互相直接覆盖。

处理顺序：

1. 停止继续修改冲突文件。
2. 先沟通谁的版本应该保留，或者两边逻辑如何合并。
3. 更新 `main`。
4. 在自己的分支合并 `main`。
5. 手动解决 Conflict。
6. 重新运行项目。
7. Commit。
8. Push。

禁止：

```bash
git push --force
```

除非团队明确知道自己在做什么，并且已经沟通过风险。

不要通过复制整个项目文件夹覆盖别人代码的方式解决 Git 冲突。这种方式很容易把其他成员已经完成的功能覆盖掉。

---

## 十二、各成员尽量避免修改的目录

为了减少冲突，建议按以下边界开发。这不是绝对禁止，但如果需要修改其他成员主要负责区域，应先沟通。

| 成员 | 主要修改目录 |
| --- | --- |
| 成员A | `frontend/` |
| 成员B | `backend/`、`scripts/init_db.py` |
| 成员C | `ai_rag/`、`data/`、`scripts/build_vector_db.py` |
| 三人共同 | `README.md`、`docs/`、`tests/integration/` |

尽量避免：

- A 未沟通就修改 `backend/app/schemas/` 中的接口模型。
- B 未沟通就修改 `frontend/src/api/` 中的前端接口封装。
- C 未沟通就修改 `backend/app/services/query_service.py` 的业务调度逻辑。
- 任意成员直接提交 `.env`、本地数据库文件或本地向量索引文件。

---

## 十三、环境变量与安全

根目录计划包含：

```text
.env.example
```

`.env.example` 可以上传 GitHub，用于说明需要哪些环境变量。

真实配置文件：

```text
.env
```

`.env` 禁止上传 GitHub。

`.env.example` 示例：

```env
DEEPSEEK_API_KEY=your_api_key_here
JWT_SECRET_KEY=your_secret_here
DATABASE_URL=sqlite:///./backend/app/db/campusflow.db
```

`.gitignore` 必须忽略：

```gitignore
.env
.venv/
venv/
__pycache__/
*.pyc
node_modules/
frontend/dist/
*.db
ai_rag/vector_db/*
.vscode/
.idea/
.DS_Store
Thumbs.db
```

禁止把以下内容提交到 GitHub：

- DeepSeek API Key
- JWT Secret
- 账号密码
- 个人 Token
- 本地 `.env`

如果发现密钥已经提交到 GitHub，应立即通知组员，并更换对应密钥。

---

## 十四、数据库和向量库协作规则

### SQLite 数据库

SQLite 的 `.db` 文件尽量不要多人直接同步修改。项目应通过脚本生成本地数据库：

```bash
python scripts/init_db.py
```

建议提交到 GitHub 的内容：

- 数据库结构代码
- SQLAlchemy Model
- 初始化脚本
- Demo 数据
- 数据库设计文档

不建议依赖上传某个人电脑上的 `campusflow.db`。

可重复生成数据库的 Demo 数据可以放在：

```text
data/demo/
```

### 向量数据库

向量数据库同理，`ai_rag/vector_db/` 不作为主要 Git 协作对象。

成员C维护：

```text
scripts/build_vector_db.py
```

其他成员通过运行该脚本生成本地向量数据库：

```bash
python scripts/build_vector_db.py
```

应该提交：

- 原始资料
- 处理脚本
- Metadata 结构
- 构建脚本
- RAG 设计文档

不建议频繁提交巨大的向量索引文件。

---

## 十五、本地启动说明

以下命令为预期方式，最终以实际代码结构为准。如果项目代码尚未完成，请先完成对应目录和脚本后再执行。

### 1. Clone 仓库

```bash
git clone <repository-url>
cd bupt-campusflow
```

### 2. 创建 Python 虚拟环境

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
```

macOS / Linux：

```bash
source .venv/bin/activate
```

### 3. 安装 Python 依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

复制 `.env.example`，生成 `.env`，并填写 DeepSeek API Key、JWT Secret 等配置。

Windows PowerShell：

```powershell
Copy-Item .env.example .env
```

macOS / Linux：

```bash
cp .env.example .env
```

### 5. 初始化 SQLite 数据库

```bash
python scripts/init_db.py
```

### 6. 如需使用 RAG，构建向量数据库

```bash
python scripts/build_vector_db.py
```

### 7. 启动 FastAPI

实际命令以项目 `main.py` 结构为准，预计方式如下：

```bash
uvicorn backend.main:app --reload
```

启动后可通过 FastAPI Swagger 检查接口：

```text
http://127.0.0.1:8000/docs
```

### 8. 启动 Vue 前端

```bash
cd frontend
npm install
npm run dev
```

### 9. 浏览器访问

浏览器访问 Vite 输出的本地地址，通常类似：

```text
http://localhost:5173/
```

---

## 十六、推荐开发顺序

### Phase 0：项目骨架

先完成基础协作结构：

- GitHub 仓库
- 目录结构
- README
- `.gitignore`
- `.env.example`
- API Contract

### Phase 1：三人并行开发

成员A先使用 Mock JSON 开发：

- 登录
- 画像
- 查询
- 结果
- 待办

成员B开发：

- FastAPI
- SQLite
- 认证
- 画像
- 待办
- 基础 API

成员C开发：

- 准备制度文件
- Chunk
- Embedding
- Vector DB
- Metadata
- 基础 RAG

### Phase 2：A + B 联调

重点联调：

- 登录
- 用户画像
- 待办
- 事务查询基础接口

### Phase 3：B + C 联调

重点联调：

- `/api/query`
- RAG
- Context
- DeepSeek

### Phase 4：三人整体联调

完整 Demo 流程：

```text
登录
→ 用户画像
→ 提问
→ RAG
→ 办理方案
→ 信息来源
→ 加入待办
→ 刷新后仍存在
```

---

## 十七、完成一个任务的 Definition of Done

一个功能不能仅仅“代码写完了”就算完成。至少满足：

- 能正常运行；
- 没有明显报错；
- 接口格式符合约定；
- 不破坏 `main` 已有功能；
- 必要的异常情况有处理；
- 已 Commit；
- 已 Push；
- 已创建或合并 PR；
- 如果接口变化，更新 `docs/api-contract.md`；
- 如果数据库结构变化，更新 `docs/database-design.md`；
- 如果 RAG 结构变化，更新 `docs/rag-design.md`。

建议每个任务完成时在 PR 中说明：

- 改了什么；
- 怎么测的；
- 有没有影响其他成员；
- 是否需要其他成员同步修改。

---

## 十八、组员每天开发前后的 Checklist

### 开始开发前

- [ ] 看 GitHub 是否有新的 PR 或变更
- [ ] `git checkout main`
- [ ] `git pull origin main`
- [ ] 同步自己的 Feature Branch
- [ ] 确认今天修改哪个模块
- [ ] 确认是否会影响其他成员接口

### 开发完成后

- [ ] 本地运行测试
- [ ] `git status` 检查
- [ ] 提交清晰 Commit
- [ ] Push Feature Branch
- [ ] 创建或更新 PR
- [ ] 告诉受影响的成员
- [ ] 如接口发生变化，更新对应 `docs`

---

## 十九、快速定位：我应该改哪里

| 我是谁 | 我主要负责 | 我优先修改 | 我需要对接谁 |
| --- | --- | --- | --- |
| 成员A | 前端交互与用户体验 | `frontend/` | 与 B 对接 HTTP API，与 C 对齐结果展示字段 |
| 成员B | 后端业务与系统工程 | `backend/`、`scripts/init_db.py` | 与 A 对接接口字段，与 C 对接 RAG 函数 |
| 成员C | AI、RAG 与个性化检索 | `ai_rag/`、`data/`、`scripts/build_vector_db.py` | 与 B 对接 Python 模块函数，与 A 对齐输出展示结构 |

最重要的协作原则：

- A 不在前端写业务规则。
- B 不重复实现 RAG。
- C 不处理用户权限和普通业务 CRUD。
- API 字段变化先更新 `docs/api-contract.md`。
- 数据库结构变化先更新 `docs/database-design.md`。
- RAG 结构变化先更新 `docs/rag-design.md`。
- 合并代码前先确认不会覆盖其他成员工作。
