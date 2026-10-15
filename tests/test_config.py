from datetime import date

import pytest

from throwback.config import ConfigError, parse_proxy, parse_settings

ENV = {
    "TELEGRAM_API_ID": "123",
    "TELEGRAM_API_HASH": "hash",
    "TELEGRAM_BOT_TOKEN": "token",
    "TELEGRAM_CHANNEL_ID": "-1001100109226",
    "TELEGRAM_SEARCH_TIMEZONE": "Asia/Yekaterinburg",
    "TELEGRAM_SEARCH_DATE_START": "2017-11-05",
    "TELEGRAM_SESSION_DIR": "storage/sessions",
    "TELEGRAM_MEMERY_FILE": "storage/memery.json",
    "TELEGRAM_IGNORE_AUTHOR": "День в истории, Альцгеймер,",
}


def test_parse_settings() -> None:
    settings = parse_settings(ENV)
    assert settings.api_id == 123
    assert settings.channel_id == -1001100109226
    assert settings.search_date_start == date(2017, 11, 5)
    assert settings.ignored_authors == {"День в истории", "Альцгеймер"}
    assert settings.test_chamber_id is None
    assert settings.proxy is None


def test_empty_test_chamber_means_none() -> None:
    assert parse_settings({**ENV, "TELEGRAM_TEST_CHAMBER_ID": ""}).test_chamber_id is None
    assert parse_settings({**ENV, "TELEGRAM_TEST_CHAMBER_ID": "42"}).test_chamber_id == 42


def test_missing_settings_are_listed() -> None:
    env = {k: v for k, v in ENV.items() if k not in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_API_ID")}
    with pytest.raises(ConfigError, match="TELEGRAM_API_ID, TELEGRAM_BOT_TOKEN"):
        parse_settings({**env, "TELEGRAM_API_ID": ""})


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("", None),
        ("socks5://127.0.0.1:2080", {"proxy_type": "socks5", "addr": "127.0.0.1", "port": 2080}),
        (
            "http://u%40x:p%3Ass@proxy:3128",
            {"proxy_type": "http", "addr": "proxy", "port": 3128, "username": "u@x", "password": "p:ss"},
        ),
    ],
)
def test_parse_proxy(url: str, expected: dict | None) -> None:
    assert parse_proxy(url) == expected


@pytest.mark.parametrize("url", ["127.0.0.1:2080", "socks5://127.0.0.1", "ftp://host:21"])
def test_parse_proxy_rejects_garbage(url: str) -> None:
    with pytest.raises(ConfigError):
        parse_proxy(url)
