import os
import smtplib
from datetime import datetime
from email.message import EmailMessage

from .time_utils import format_shanghai


class EmailConfigError(RuntimeError):
    pass


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _smtp_port() -> int:
    raw = os.getenv("SMTP_PORT", "587").strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise EmailConfigError("SMTP_PORT 配置不正确") from exc


def _smtp_security() -> str:
    configured = os.getenv("SMTP_SECURITY", "").strip().lower()
    if configured:
        if configured not in {"ssl", "starttls", "none"}:
            raise EmailConfigError("SMTP_SECURITY 仅支持 ssl、starttls 或 none")
        return configured
    return "starttls" if _truthy(os.getenv("SMTP_USE_TLS", "true")) else "none"


def _required_config() -> dict[str, str | int | bool]:
    host = os.getenv("SMTP_HOST", "").strip()
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    from_addr = os.getenv("SMTP_FROM", "").strip() or username
    if not host or not username or not password or not from_addr:
        raise EmailConfigError("SMTP 未完整配置")
    return {
        "host": host,
        "port": _smtp_port(),
        "username": username,
        "password": password,
        "from_addr": from_addr,
        "security": _smtp_security(),
    }


def _display_time(value: datetime) -> str:
    return format_shanghai(value)


def send_deadline_email(*, to_email: str, title: str, due_at: datetime, notes: str = "") -> None:
    config = _required_config()
    message = EmailMessage()
    message["Subject"] = "【邮智办】待办事项即将到期提醒"
    message["From"] = str(config["from_addr"])
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "你好，你在“邮智办”中的待办事项即将到期：",
                "",
                f"事项：{title}",
                f"截止时间：{_display_time(due_at)}",
                f"备注：{notes or '无'}",
                "",
                "请及时确认办理进度。",
                "",
                "—— 邮智办",
            ]
        )
    )

    smtp_class = smtplib.SMTP_SSL if config["security"] == "ssl" else smtplib.SMTP
    with smtp_class(str(config["host"]), int(config["port"]), timeout=20) as smtp:
        if config["security"] == "starttls":
            smtp.starttls()
        smtp.login(str(config["username"]), str(config["password"]))
        smtp.send_message(message)
