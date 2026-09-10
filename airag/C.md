# C 模块说明

C 模块负责“邮智办”的 AI / RAG 处理。

## 1. 服务端口

C 默认运行在：

`http://127.0.0.1:8001`

启动命令：

```powershell
python -m uvicorn airag.app:app --host 127.0.0.1 --port 8001
```

## 2. C 接收什么

核心接口：

`POST /generate`

完整地址：

`http://127.0.0.1:8001/generate`

请求格式：

```json
{
  "question": "用户问题",
  "profile": {
    "college": "学院",
    "grade": "年级",
    "education_level": "本科/研究生",
    "campus": "校区"
  },
  "affairs": []
}
```

字段说明：

- `question`：用户自然语言问题
- `profile`：学生画像，用于 Metadata Filtering
- `affairs`：B 从 SQLite 中提供的结构化事务数据

## 3. C 内部处理流程

```text
question + profile + affairs
↓
Metadata Filtering
↓
Embedding
↓
Vector Search
↓
Top-K Retrieval
↓
Context Builder
↓
Prompt
↓
DeepSeek
↓
生成 answer
```

同时：

```text
Retrieved Chunks → sources
B affairs → plans
程序规则 → warnings
```

## 4. C 输出什么

返回格式：

```json
{
  "answer": "AI 生成的回答",
  "plans": [],
  "sources": [],
  "warnings": [],
  "mode": "rag"
}
```

字段说明：

- `answer`：DeepSeek 根据 RAG 内容生成的回答
- `plans`：根据 B 提供的 affairs 生成办理方案
- `sources`：RAG 检索命中的真实来源
- `warnings`：缺失信息或 fallback 提示
- `mode`：固定为 `rag`

## 5. API 调用流程

当前完整调用关系：

```text
A 前端
↓
B 后端：8000
↓
POST http://127.0.0.1:8001/generate
↓
C AI/RAG：8001
↓
Metadata Filtering
↓
Embedding + Vector Search
↓
Context Builder
↓
DeepSeek API
↓
C 返回 QueryResult
↓
B
↓
A
```

## 6. DeepSeek API

DeepSeek API Key 只需要配置在运行 C 的环境中：

```powershell
$env:DEEPSEEK_API_KEY="你的Key"
```

A 和 B 不需要知道 DeepSeek API Key。

调用关系：

```text
A
↓
B
↓
C
↓
DeepSeek API
↓
C
↓
B
↓
A
```