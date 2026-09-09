# 邮智办：成员 B 后端工程

根据分工说明实现 FastAPI + SQLAlchemy + SQLite 后端。包含学生注册/登录、JWT、学生/管理员权限、用户画像、事务 CRUD、待办 CRUD、个人查询历史、管理员审计日志以及 `/api/query` 调度。

**交付状态：代码及集成测试已编写；本次环境无法下载运行依赖，因此未完成接口集成测试。请按下面步骤安装后运行测试。**

默认 `demo` 模式只读取结构化事务并做简单文字匹配，没有接入真实学校制度、向量检索或 DeepSeek。切换 `http` 模式后调用 C 的 RAG 服务；C 负责 DeepSeek 密钥、Prompt、检索和生成。无需重复实现 C 的向量知识库。

## 1. Windows 启动（Python 3.11 或更高）

在本目录打开 PowerShell，依次执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:JWT_SECRET_KEY = (.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))")
$env:RAG_MODE = 'demo'
.\.venv\Scripts\python.exe -m app.create_admin admin
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

管理员创建脚本会隐藏输入密码；没有默认管理员密码。注册接口只能创建学生，不接受 role。JWT 有效期两小时。开发命令每次生成不同密钥会令旧 token 失效；部署时在服务环境变量中配置固定随机密钥，不提交到 Git。

打开 [交互式接口文档](http://127.0.0.1:8000/docs)。先通过登录接口获取 `data.access_token`，再点击 Authorize 输入 token。

SQLite 数据库首次启动时创建在当前工作目录，文件名为 `youzhiban.db`（默认配置）。

后端自动读取项目根目录的 `.env`；已经设置的系统环境变量优先。本地真实 `.env` 不提交到 GitHub。

若修改数据库结构，需另外编写迁移；当前 `create_all` 只负责新建缺失表，不会更新已有表结构。

## 2. 给 A 的接口约定

统一成功返回 `{"code":0,"message":"ok","data":...}`；失败使用实际 HTTP 错误状态，并返回相同外层字段。需登录的接口附带 `Authorization: Bearer <token>`。列表返回数组，支持 `offset=0&limit=20`，limit 最大 100。PUT 是完整替换，省略的字段恢复其默认值。

| 方法 | 路径 | 功能 / 权限 |
|---|---|---|
| GET | /api/health | 状态，无需登录 |
| POST | /api/auth/register | 注册学生，无需登录 |
| POST | /api/auth/login | JSON 登录，无需登录 |
| GET | /api/auth/me | 当前用户 |
| GET / PUT / DELETE | /api/profile | 获取、新建或替换、删除自己的画像 |
| GET | /api/affairs?q=关键词 | 事务目录（可见不代表符合办理条件） |
| GET | /api/affairs/{id} | 事务详情 |
| POST | /api/admin/affairs | 新建事务，管理员 |
| PUT / DELETE | /api/admin/affairs/{id} | 替换/删除事务，管理员 |
| GET | /api/admin/logs | 操作日志，管理员 |
| GET / POST | /api/todos | 个人待办列表/创建 |
| GET / PUT / DELETE | /api/todos/{id} | 个人待办详情/替换/删除 |
| POST | /api/query | 查询并保存成功结果 |
| GET | /api/history | 自己的查询历史 |
| GET / DELETE | /api/history/{id} | 历史详情/删除 |

登录及注册：`{"username":"student01","password":"your-password"}`。

画像：`{"college":"计算机学院","grade":"2024","education_level":"本科","campus":"沙河"}`。这些值是团队联调约定；B 的结构化过滤和 C 的 Metadata 应使用相同值。

待办：`{"title":"准备材料","notes":"备注","completed":false,"due_at":null}`，due_at 可传 ISO 8601 日期时间。

管理员创建事务示例（纯演示数据，不是真实政策）：

```json
{
  "title": "测试事务",
  "description": "仅用于课程演示",
  "location": "演示办公楼",
  "room": "101",
  "contact": "演示联系人",
  "office_hours": "演示时间",
  "materials": ["测试材料"],
  "steps": ["准备测试材料", "提交测试申请"],
  "sources": [{"title": "演示来源", "reference": "demo:only"}],
  "eligibility": {"campus": ["沙河"]}
}
```

eligibility 仅允许 college、grade、education_level、campus；空字典或空列表不限制。多字段之间是 AND，同字段多个值是 OR。画像缺失不满足非空限制。过滤是办理条件筛选，非保密访问控制；已登录用户均可查看事务目录。

查询请求：`{"question":"如何办理测试事务？","affair_id":1}`。affair_id 可省略；demo 模式省略时使用简单标题/描述匹配。没有事务数据时返回空 plans 和明确提示。

前端 fetch 示例：

```javascript
const response = await fetch('http://127.0.0.1:8000/api/query', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
  body: JSON.stringify({ question: '如何办理测试事务？', affair_id: 1 })
});
const body = await response.json();
if (!response.ok) throw new Error(body.message);
console.log(body.data.plans, body.data.sources, body.data.warnings);
```

## 3. 给 C 的对接约定

```powershell
$env:RAG_MODE = 'http'
$env:RAG_URL = 'http://127.0.0.1:8001/generate'
$env:RAG_API_KEY = '团队约定的服务密钥'
```

重启后端。B 向配置的完整 URL 发送 POST JSON：

```json
{"question":"用户问题","profile":{"college":"","grade":"","education_level":"","campus":""},"affairs":[]}
```

affairs 是已按画像筛选的结构化事务对象列表，字段对应事务表；指定 affair_id 时最多一个。C 可独立检索向量库，但应遵守画像条件，优先使用 B 提供的地点、房间、负责人、办公时间等结构化事实。这里只发送画像业务字段，不发送用户密码、JWT 或用户 id。

C 必须直接返回以下 JSON（不加 B 的 code/data 外层，不加 Markdown 代码块）：

```json
{
  "answer": "回答正文",
  "plans": [{
    "affair_id": 1,
    "title": "事务名",
    "materials": ["材料"],
    "steps": ["步骤"],
    "location": "地点",
    "room": "房间",
    "contact": "负责人",
    "office_hours": "办公时间",
    "sources": [{"title": "文件名", "reference": "文件页码或来源地址"}]
  }],
  "sources": [{"title": "文件名", "reference": "文件页码或来源地址"}],
  "warnings": [],
  "mode": "rag"
}
```

计划可为空，非结构化事务的 affair_id 可以为 null。完整校验模型见 `app/schemas.py`。超时返回 504，上游错误或格式错误返回 502；失败不会保存为成功历史。B 进行结构校验，来源真实性和生成内容准确性仍需 C 验证。

## 4. 数据库结构

| 表 | 主键与关联 | 数据 |
|---|---|---|
| users | id；username 唯一 | scrypt 密码哈希、角色、创建时间 |
| profiles | user_id → users.id，一对一 | 学院、年级、培养层次、校区 |
| affairs | id | 事务事实及 JSON 材料、流程、来源、适用条件 |
| todos | id；user_id → users.id | 标题、备注、完成状态、到期时间 |
| query_history | id；user_id → users.id | 问题、结果 JSON 快照、时间 |
| audit_logs | id；user_id → users.id | 创建/更新/删除动作及事务快照 |

事务变更与审计日志在同一数据库事务提交。删除事务后仍保留审计快照和历史结果。待办/历史的详情、修改、删除均验证所属用户。

## 5. 验证与演示顺序

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

测试覆盖注册重复、密码错误、过期 token、注册提权拦截、画像隔离、跨用户待办访问、管理员权限、画像条件筛选、查询历史隔离、日志保留，以及 RAG 正常响应/错误格式/超时。使用内存业务数据库，不写真实业务数据。

建议演示：创建管理员 → 管理员登录并添加上述测试事务 → 注册学生 → 保存沙河校区画像 → 查询测试事务 → 创建并完成待办 → 查看历史 → 管理员查看日志。

本工程按课程项目规模实现。没有包含前端、C 的真实知识库、生产环境登录限流/密码找回/令牌撤销及数据库迁移。上线前应补齐相关能力。

技术参考：[FastAPI JWT 文档](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/)；[SQLAlchemy SQLite 文档](https://docs.sqlalchemy.org/en/20/dialects/sqlite.html)。
