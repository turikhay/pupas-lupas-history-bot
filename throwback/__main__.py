import argparse
import asyncio
import logging
import os
import random
import sys
from collections.abc import Sequence

from telethon import TelegramClient
from telethon import types as tg

from .config import ConfigError, Settings, parse_settings, read_env
from .dates import today_at
from .memery import JsonMemery, Memery, ReadOnlyMemery
from .model import Group
from .runner import DryRun, Publisher, post_throwback
from .telegram import BotPublisher, ChannelHistory

EXIT_POSTED = 0
EXIT_ERROR = 1  # also what Python exits with on an uncaught exception
EXIT_NOTHING_TO_POST = 3  # 2 is argparse's exit code for bad arguments


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m throwback",
        description="Reposts a meme published on the same day in a past year (#MemeThrowback).",
        epilog=f"Exit codes: {EXIT_POSTED} posted, {EXIT_NOTHING_TO_POST} nothing to post, {EXIT_ERROR} error.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="pick a post and print it with its caption, without posting or remembering anything",
    )
    return parser.parse_args(argv)


def exit_code(posted: Group | None) -> int:
    return EXIT_POSTED if posted is not None else EXIT_NOTHING_TO_POST


def client(settings: Settings, name: str) -> TelegramClient:
    return TelegramClient(
        session=os.path.join(settings.session_dir, name),
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        proxy=settings.proxy,  # type: ignore[arg-type]  # Telethon's annotation omits its None default
    )


async def main(dry_run: bool) -> int:
    try:
        settings = parse_settings(read_env())
    except ConfigError as e:
        logging.error(e)
        return EXIT_ERROR
    async with client(settings, "user") as user:
        channel: tg.Channel = await user.get_entity(settings.channel_id)  # type: ignore[assignment]
        history = ChannelHistory(user, channel, settings.tz)
        memery: Memery = JsonMemery(settings.memery_file)

        async def post(publisher: Publisher, memery: Memery) -> int:
            posted = await post_throwback(
                today=today_at(settings.tz),
                start=settings.search_date_start,
                history=history,
                publisher=publisher,
                memery=memery,
                ignored_authors=settings.ignored_authors,
                tz=settings.tz,
                rng=random.Random(),
            )
            return exit_code(posted)

        if dry_run:
            logging.info("Dry run: nothing will be posted or remembered")
            return await post(DryRun(), ReadOnlyMemery(memery))

        bot = client(settings, "bot")
        # start() and disconnect() are coroutines, but Telethon annotates them as sync
        await bot.start(bot_token=settings.bot_token)  # type: ignore[misc]
        try:
            bot_channel = await bot.get_input_entity(settings.channel_id)
            test_chamber_id = settings.test_chamber_id
            if test_chamber_id is None:
                return await post(BotPublisher(bot, bot_channel, bot_channel), memery)
            logging.info("Test run: posting to the test chamber, without replies and without remembering")
            target = await bot.get_input_entity(tg.PeerChat(test_chamber_id))
            return await post(BotPublisher(bot, bot_channel, target, keep_replies=False), ReadOnlyMemery(memery))
        finally:
            await bot.disconnect()  # type: ignore[misc]


def run(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    sys.exit(asyncio.run(main(args.dry_run)))


if __name__ == "__main__":
    run()
