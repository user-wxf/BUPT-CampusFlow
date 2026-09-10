import os
from typing import Any

import httpx


DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_CHAT_COMPLETIONS_PATH = "/chat/completions"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_TIMEOUT_SECONDS = 30.0


class DeepSeekError(RuntimeError):
    pass


def _api_key(explicit_key: str | None = None) -> str:
    key = explicit_key or os.getenv("DEEPSEEK_API_KEY", "")
    if not key.strip():
        raise DeepSeekError("DEEPSEEK_API_KEY is not configured")
    return key.strip()


def _model(explicit_model: str | None = None) -> str:
    model = explicit_model or os.getenv("DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    if not model.strip():
        raise DeepSeekError("DeepSeek model is empty")
    return model.strip()


def _extract_content(payload: dict[str, Any]) -> str:
    try:
        content = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DeepSeekError("DeepSeek response format is invalid") from exc
    if not isinstance(content, str) or not content.strip():
        raise DeepSeekError("DeepSeek response content is empty")
    return content.strip()


def call_deepseek(
    prompt: str,
    *,
    model: str | None = None,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    api_key: str | None = None,
    client: httpx.Client | None = None,
) -> str:
    text = prompt.strip()
    if not text:
        raise DeepSeekError("Prompt cannot be empty")

    key = _api_key(api_key)
    selected_model = _model(model)
    url = DEEPSEEK_BASE_URL + DEEPSEEK_CHAT_COMPLETIONS_PATH
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": selected_model,
        "messages": [{"role": "user", "content": text}],
        "stream": False,
    }

    owns_client = client is None
    active_client = client or httpx.Client(timeout=timeout)
    try:
        response = active_client.post(url, headers=headers, json=body)
        response.raise_for_status()
        return _extract_content(response.json())
    except httpx.TimeoutException as exc:
        raise DeepSeekError("DeepSeek request timed out") from exc
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        raise DeepSeekError(f"DeepSeek HTTP request failed with status {status_code}") from exc
    except httpx.HTTPError as exc:
        raise DeepSeekError("DeepSeek HTTP request failed") from exc
    except ValueError as exc:
        raise DeepSeekError("DeepSeek response is not valid JSON") from exc
    finally:
        if owns_client:
            active_client.close()
