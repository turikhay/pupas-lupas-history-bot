import asyncio
import random
from datetime import UTC, date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from tests.factories import group, post
from throwback.memery import JsonMemery
from throwback.model import Group, Post
from throwback.runner import caption, post_throwback

TZ = ZoneInfo("Asia/Yekaterinburg")
TODAY = date(2026, 10, 15)
START = date(2023, 10, 16)  # two available years: 2025 and 2024
NOON_2025 = datetime(2025, 10, 15, 7, tzinfo=UTC)


class FakeSource:
    username = "pupaslupas"

    def __init__(self, days: dict[date, list[Post]]):
        self.days = days
        self.fetched: list[date] = []
        self.reposted: list[tuple[Group, str]] = []

    async def fetch_day(self, day: date) -> list[Post]:
        self.fetched.append(day)
        return self.days.get(day, [])

    async def repost(self, group: Group, caption: str) -> None:
        self.reposted.append((group, caption))


def run(source: FakeSource, memery: JsonMemery, seed: int = 0) -> Group | None:
    return asyncio.run(post_throwback(TODAY, START, source, memery, frozenset({"Альцгеймер"}), TZ, random.Random(seed)))


@pytest.fixture
def memery(tmp_path: Path) -> JsonMemery:
    return JsonMemery(str(tmp_path / "memery.json"))


def test_reposts_the_best_group_and_remembers_it(memery: JsonMemery) -> None:
    source = FakeSource(
        {
            date(2025, 10, 15): [
                post(10, reactions={"🔥": 1}, date=NOON_2025),
                post(11, grouped_id=99, reactions={"🔥": 5}, reply_to=3, date=NOON_2025),
                post(12, grouped_id=99, date=NOON_2025),
            ]
        }
    )
    posted = run(source, memery)
    assert posted is not None and [p.id for p in posted.posts] == [11, 12]
    assert source.reposted == [(posted, "[2025](https://t.me/pupaslupas/11) #MemeThrowback")]
    assert memery.is_posted_already(99)
    assert memery.is_posted_already(3)
    assert not memery.is_posted_already(10)


@pytest.mark.parametrize("seed", range(5))
def test_skips_posted_and_own_groups_then_falls_back_to_another_year(memery: JsonMemery, seed: int) -> None:
    memery.store(10)
    source = FakeSource(
        {
            date(2025, 10, 15): [post(10), post(11, author="Альцгеймер"), post(12, text="#MemeThrowback")],
            date(2024, 10, 15): [post(20)],
        }
    )
    posted = run(source, memery, seed)
    assert posted is not None and posted.key == 20


def test_returns_none_when_every_year_is_exhausted(memery: JsonMemery) -> None:
    source = FakeSource({date(2025, 10, 15): [post(10)]})
    memery.store(10)
    assert run(source, memery) is None
    assert sorted(source.fetched) == [date(2024, 10, 15), date(2025, 10, 15)]
    assert source.reposted == []


def test_caption_year_is_in_the_channel_timezone() -> None:
    # 20:00 UTC on Dec 31 is already Jan 1 in Yekaterinburg
    new_year = group(post(7, date=datetime(2019, 12, 31, 20, tzinfo=UTC)))
    assert caption(new_year, "pupaslupas", TZ) == "[2020](https://t.me/pupaslupas/7) #MemeThrowback"
