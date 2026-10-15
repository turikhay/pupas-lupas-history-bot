import asyncio
import logging
import os
import random
import sys

from telethon import TelegramClient
from telethon import types as tg

from .config import Settings, parse_settings, read_env
from .dates import today_at
from .memery import JsonMemery
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
            target = (
                await bot.get_entity(tg.PeerChat(settings.test_chamber_id))
                if settings.test_chamber_id is not None
                else await bot.get_entity(tg.PeerChannel(channel.id))
            )
            await post_throwback(
                today=today_at(settings.tz),
                start=settings.search_date_start,
                source=Channel(user, bot, channel, target, settings.tz),
                memery=JsonMemery(settings.memery_file),
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
