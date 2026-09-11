from functools import lru_cache
import os
from pathlib import Path

from dotenv import dotenv_values, load_dotenv


@lru_cache(maxsize=1)
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


@lru_cache(maxsize=1)
def load_project_env() -> Path:
    env_path = project_root() / ".env"
    load_dotenv(env_path, override=False)
    if env_path.exists():
        for key, value in dotenv_values(env_path).items():
            if value is not None and not os.getenv(key):
                os.environ[key] = value
    return env_path
