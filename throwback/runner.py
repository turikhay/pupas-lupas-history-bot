import logging
import random
from collections.abc import Collection
from datetime import date, tzinfo
from typing import Protocol

from .captions import Caption, build_caption
from .dates import available_years, years_ago
from .memery import Memery
from .model import EntityKind, Group, Post
from .selection import can_be_reposted, group_posts, rank


class History(Protocol):
    @property
    def username(self) -> str | None: ...

    async def fetch_day(self, day: date) -> list[Post]: ...


class Publisher(Protocol):
    async def repost(self, group: Group, caption: Caption) -> None: ...


class DryRun:
    """Prints what would be reposted instead of reposting it."""

    async def repost(self, group: Group, caption: Caption) -> None:
        # The last link is the one to the original
        original = [entity.url for entity in caption.entities if entity.kind is EntityKind.TEXT_URL][-1]
        media = ", ".join(post.media for post in group.posts)
        print(f"Would repost {original} ({media}) with caption:\n{caption.text}")


async def post_throwback(
    today: date,
    start: date,
    history: History,
    publisher: Publisher,
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
            for group in group_posts(await history.fetch_day(target_date))
            if can_be_reposted(group, ignored_authors, is_wednesday)
        ]
        if not groups:
            logging.info(f"Skipping date: {target_date}")
            continue
        for group in rank(groups, rng):
            if memery.is_posted_already(group.key):
                logging.info(f"Already posted: {group.key}")
                continue
            logging.info(f"Picked: {group}")
            await publisher.repost(group, build_caption(group, history.username, tz))
            memery.store(group.key)
            if group.reply_to:
                # Reposting a reply quotes the original, so don't repost the original later
                memery.store(group.reply_to)
            return group
        logging.info(f"Nothing to post from the selected date: {target_date}")
    logging.error("Couldn't find anything to post. Please check settings")
    return None
