"""B→C 服务边界。C 负责检索、上下文构建和 DeepSeek 调用。"""
import os
import httpx
from fastapi import HTTPException
from pydantic import ValidationError
from .schemas import QueryResult


def generate(question: str, profile: dict, affairs: list[dict]) -> dict:
    mode = os.getenv('RAG_MODE', 'demo')
    if mode == 'demo':
        fields = ('id', 'title', 'materials', 'steps', 'location', 'room', 'contact', 'office_hours', 'sources')
        plans = []
        for affair in affairs:
            plan = {k: affair[k] for k in fields}
            plan['affair_id'] = plan.pop('id')
            plans.append(plan)
        return QueryResult(answer='以下为结构化事务信息，请核对适用条件。' if plans else '未找到匹配事务，请补充画像或指定事务。',
                           plans=plans, sources=[s for p in plans for s in p['sources']], mode='demo',
                           warnings=['演示模式：未调用 RAG 或 DeepSeek，不构成真实校务政策答复。']).model_dump(mode='json')
    url = os.getenv('RAG_URL', '')
    if mode != 'http' or not url:
        raise HTTPException(503, 'RAG 服务未正确配置')
    headers = {'Authorization': 'Bearer ' + os.environ['RAG_API_KEY']} if os.getenv('RAG_API_KEY') else {}
    try:
        with httpx.Client(timeout=httpx.Timeout(45, connect=5), follow_redirects=False) as client:
            response = client.post(url, headers=headers, json={'question': question, 'profile': profile, 'affairs': affairs})
            response.raise_for_status()
            result = QueryResult.model_validate(response.json())
            if result.mode != 'rag':
                raise ValueError('Expected RAG result')
            return result.model_dump(mode='json')
    except httpx.TimeoutException:
        raise HTTPException(504, '智能查询超时，请稍后重试')
    except (httpx.HTTPError, ValidationError, ValueError):
        raise HTTPException(502, '智能查询服务异常或返回格式不正确')
