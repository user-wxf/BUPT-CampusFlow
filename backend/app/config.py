import os
from functools import lru_cache
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


@lru_cache(maxsize=1)
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def load_project_env() -> Path:
    env_path = project_root() / ".env"
    load_dotenv(env_path, override=False)
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if value is not None and not os.getenv(key):
                os.environ[key] = value
    return env_path


def normalized_rag_mode() -> str:
    mode = os.getenv("RAG_MODE", "demo").strip().lower()
    if mode in {"http", "rag"}:
        return "http"
    if mode in {"demo", ""}:
        return "demo"
    return mode


def database_url() -> str:
    load_project_env()
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        return "sqlite:///" + (project_root() / "backend" / "youzhiban.db").as_posix()
    prefix = "sqlite:///"
    if not raw.startswith(prefix):
        return raw
    path_text = raw[len(prefix):]
    if not path_text or path_text.startswith("/") or Path(path_text).is_absolute():
        return raw
    return prefix + (project_root() / path_text).as_posix()
