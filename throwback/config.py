import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from dotenv import dotenv_values

REQUIRED = (
    "TELEGRAM_API_ID",
    "TELEGRAM_API_HASH",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHANNEL_ID",
    "TELEGRAM_SEARCH_TIMEZONE",
    "TELEGRAM_SEARCH_DATE_START",
    "TELEGRAM_SESSION_DIR",
    "TELEGRAM_MEMERY_FILE",
)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Settings:
    api_id: int
    api_hash: str
    bot_token: str
    channel_id: int
    tz: ZoneInfo
    search_date_start: date
    session_dir: str
    memery_file: str
    ignored_authors: frozenset[str]
    test_chamber_id: int | None
    proxy: dict[str, Any] | None


def read_env() -> dict[str, str | None]:
    return {
        **dotenv_values(".env.defaults"),
        **dotenv_values(".env"),
        **os.environ,
    }


def parse_settings(env: Mapping[str, str | None]) -> Settings:
    missing = [key for key in REQUIRED if not env.get(key)]
    if missing:
        raise ConfigError(f"Missing settings: {', '.join(missing)}")

    def get(key: str) -> str:
        return env.get(key) or ""

    test_chamber_id = get("TELEGRAM_TEST_CHAMBER_ID").strip()
    return Settings(
        api_id=int(get("TELEGRAM_API_ID")),
        api_hash=get("TELEGRAM_API_HASH"),
        bot_token=get("TELEGRAM_BOT_TOKEN"),
        channel_id=int(get("TELEGRAM_CHANNEL_ID")),
        tz=ZoneInfo(get("TELEGRAM_SEARCH_TIMEZONE")),
        search_date_start=datetime.strptime(get("TELEGRAM_SEARCH_DATE_START"), "%Y-%m-%d").date(),
        session_dir=get("TELEGRAM_SESSION_DIR"),
        memery_file=get("TELEGRAM_MEMERY_FILE"),
        ignored_authors=frozenset(
            author.strip() for author in get("TELEGRAM_IGNORE_AUTHOR").split(",") if author.strip()
        ),
        test_chamber_id=int(test_chamber_id) if test_chamber_id else None,
        proxy=parse_proxy(get("TELEGRAM_PROXY")),
    )


def parse_proxy(url: str) -> dict[str, Any] | None:
    """socks5://[user:password@]host:port (also socks4, http) into Telethon's proxy dict."""
    if not url:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("socks5", "socks4", "http") or not parts.hostname or not parts.port:
        raise ConfigError(f"TELEGRAM_PROXY must look like socks5://host:port, got {parts.scheme}://…")
    proxy: dict[str, Any] = {"proxy_type": parts.scheme, "addr": parts.hostname, "port": parts.port}
    if parts.username:
        proxy["username"] = unquote(parts.username)
        proxy["password"] = unquote(parts.password or "")
    return proxy
