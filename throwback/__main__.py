import asyncio
import logging
import os
import random
import sys

from telethon import TelegramClient
from telethon import types as tg

from .config import Settings, parse_settings, read_env
from .dates import today_at
from .memery import JsonMemery, Memery, ReadOnlyMemery
from .runner import post_throwback
from .telegram import Channel


def client(settings: Settings, name: str) -> TelegramClient:
    return TelegramClient(
        session=os.path.join(settings.session_dir, name),
        api_id=settings.api_id,
        api_hash=settings.api_hash,
        proxy=settings.proxy,  # type: ignore[arg-type]  # Telethon's annotation omits its None default
    )


async def main() -> int:
    settings = parse_settings(read_env())
    user = client(settings, "user")
    bot = client(settings, "bot")
    # start() and disconnect() are coroutines, but Telethon annotates them as sync
    await bot.start(bot_token=settings.bot_token)  # type: ignore[misc]
    try:
        async with user:
            channel: tg.Channel = await user.get_entity(settings.channel_id)  # type: ignore[assignment]
            bot_channel = await bot.get_input_entity(settings.channel_id)
            memery: Memery = JsonMemery(settings.memery_file)
            test_chamber_id = settings.test_chamber_id
            if test_chamber_id is not None:
                logging.info("Test run: posting to the test chamber, without replies and without remembering")
                target = await bot.get_input_entity(tg.PeerChat(test_chamber_id))
                memery = ReadOnlyMemery(memery)
            else:
                target = bot_channel
            await post_throwback(
                today=today_at(settings.tz),
                start=settings.search_date_start,
                source=Channel(
                    user, bot, channel, bot_channel, target, settings.tz, keep_replies=test_chamber_id is None
                ),
                memery=memery,
                ignored_authors=settings.ignored_authors,
                tz=settings.tz,
                rng=random.Random(),
            )
    finally:
        await bot.disconnect()  # type: ignore[misc]
    return 0


def run() -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO)
    sys.exit(asyncio.run(main()))


if __name__ == "__main__":
    run()
