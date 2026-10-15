import logging
import random
from collections.abc import Collection
from datetime import date, tzinfo
from typing import Protocol

from .captions import Caption, build_caption
from .dates import available_years, years_ago
from .memery import Memery
from .model import Group, Post
from .selection import can_be_reposted, group_posts, rank


class Source(Protocol):
    @property
    def username(self) -> str | None: ...

    async def fetch_day(self, day: date) -> list[Post]: ...

    async def repost(self, group: Group, caption: Caption) -> None: ...


async def post_throwback(
    today: date,
    start: date,
    source: Source,
    memery: Memery,
    ignored_authors: Collection[str],
    tz: tzinfo,
    rng: random.Random,
) -> Group | None:
    """Reposts the best unposted group from the same day in a random past year; returns it, or None."""
    is_wednesday = today.weekday() == 2
    years = available_years(today, start)
    while years:
        target_date = years_ago(years.pop(rng.randrange(len(years))), today)
        logging.info(f"Selected date: {target_date}")
        groups = [
            group
            for group in group_posts(await source.fetch_day(target_date))
            if can_be_reposted(group, ignored_authors, is_wednesday)
        ]
        if not groups:
            logging.info(f"Skipping date: {target_date}")
            continue
        for group in rank(groups, rng):
            if memery.is_posted_already(group.key):
                logging.info(f"Already posted: {group.key}")
                continue
            logging.info(f"Posting: {group}")
            await source.repost(group, build_caption(group, source.username, tz))
            memery.store(group.key)
            if group.reply_to:
                # Reposting a reply quotes the original, so don't repost the original later
                memery.store(group.reply_to)
            return group
        logging.info(f"Nothing to post from the selected date: {target_date}")
    logging.error("Couldn't find anything to post. Please check settings")
    return None
