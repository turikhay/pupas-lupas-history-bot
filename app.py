from collections import OrderedDict
import logging
import datetime
from sys import stdout
from dotenv import dotenv_values
from os import environ, path
from zoneinfo import ZoneInfo
from random import choice
from telethon import TelegramClient, types as tg, hints

from dateutils import today_at, years_ago, to_datetime
from memery.json_memery import JsonMemory
from message import GroupedMessages
from supported_media import is_supported_media

config = {
    **dotenv_values(".env.defaults"),
    **dotenv_values(".env"), 
    **environ,
}
logging.basicConfig(stream=stdout, level=logging.INFO)

api_id: int = int(config["TELEGRAM_API_ID"]) # type: ignore
api_hash: str = config["TELEGRAM_API_HASH"] # type: ignore
tz: datetime.timezone = ZoneInfo(config["TELEGRAM_SEARCH_TIMEZONE"]) # type: ignore
session_dir: str = config["TELEGRAM_SESSION_DIR"] # type: ignore

memery = JsonMemory(
    config["TELEGRAM_MEMERY_FILE"] # type: ignore
)
user = TelegramClient(
    session=path.join(session_dir, "user"),
    api_id=api_id,
    api_hash=api_hash
)
bot = TelegramClient(
    session=path.join(session_dir, "bot"),
    api_id=api_id,
    api_hash=api_hash
).start(
    bot_token=config["TELEGRAM_BOT_TOKEN"] # type: ignore
)

test_chamber_id = config["TELEGRAM_TEST_CHAMBER_ID"] if "TELEGRAM_TEST_CHAMBER_ID" in config else None
channel_id: int = int(config["TELEGRAM_CHANNEL_ID"]) # type: ignore
search_date_start = datetime.datetime.strptime(config["TELEGRAM_SEARCH_DATE_START"], '%Y-%m-%d') # type: ignore
ignored_author = config["TELEGRAM_IGNORE_AUTHOR"] # type: ignore

async def main():
    years_max = (datetime.datetime.now(tz) - search_date_start.replace(tzinfo=tz)).days // 365
    years_set = set(range(1, years_max))
    test_chamber: hints.EntityLike | None = None
    if test_chamber_id != None:
        test_chamber = await bot.get_entity(tg.PeerChat(int(test_chamber_id)))
    channel: tg.Channel = await user.get_entity(channel_id) # type: ignore
    while len(years_set) > 0:
        target_year = choice(list(years_set))
        target_date = years_ago(target_year, today_at(tz))
        logging.info(f"Selected date: {target_date}")
        collected = list(await collect_messages_at_date(channel, target_date))
        if len(collected) == 0:
            logging.info(f"Skipping date: {target_date}")
            years_set.remove(target_year)
            continue
        group: GroupedMessages | None = choice(collected)
        while memery.is_posted_already(group.id):
            collected.remove(group)
            if len(collected) == 0:
                group = None
                break
            group = choice(collected)
        if group == None:
            logging.info(f"Skipping date because it's fully reposted: {target_date}")
            years_set.remove(target_year)
            continue
        logging.info(f"Selected group: {group}")
        await repost(channel.id, group, test_chamber)
        memery.store(group.id)
        return
    logging.error("Couldn't find anything to post. Please check settings")

async def repost(channel_id: int, group: GroupedMessages, target: hints.EntityLike | None = None) -> None:
    channel = await bot.get_entity(tg.PeerChannel(channel_id))
    posts = group.messages
    # TODO: use references, do not download
    match len(posts):
        case 0:
            raise Exception("No messages in the group")
        case 1:
            artifact = await user.download_media(posts[0], file="/tmp/")
        case _:
            artifact = []
            for post in posts:
                artifact.append(await user.download_media(post, file="/tmp/"))
    await bot.send_message(
        target if target != None else channel,
        message=f"[{group.date.year}](https://t.me/{channel.username}/{group.msg_id}) #MemeThrowback", # type: ignore
        file=artifact, # type: ignore
        silent=True,
    )
    pass

async def collect_messages_at_date(channel: tg.Channel, target_date: datetime.date) -> list[GroupedMessages]:
    target_time = to_datetime(target_date, tz)
    _first_post = await user.get_messages(channel, limit=1, offset_date=target_time, filter=tg.InputMessagesFilterPhotoVideo)
    if len(_first_post) == 0:
        logging.warning(f"get_messages returned empty list for {channel}")
        return []
    first_post: tg.Message = _first_post[0]
    delta: datetime.timedelta = abs(first_post.date - target_time) # type: ignore
    if delta.seconds > 3600 * 24 * 3:
        logging.warning(f"Time difference between target_date and post #{first_post.id} is {delta} (too high!)")
        return []
    posts: OrderedDict[int, GroupedMessages] = OrderedDict()
    next_time = target_time + datetime.timedelta(1)
    async for post in user.iter_messages(channel, reverse=True, offset_id=first_post.id, limit=100):
        print(f"Found post: {post.id}")
        assert isinstance(post, tg.Message)
        assert isinstance(post.date, datetime.datetime)
        if post.date < target_time:
            logging.info(f"Skipping because it's before the target date {post.date} > {target_time}")
            continue
        if post.date >= next_time:
            logging.info(f"Found next date, stopping: {post.date} > {next_time}")
            break
        if not can_be_reposted(post):
            continue
        group_id = post.grouped_id if post.grouped_id != None else post.id
        if group_id not in posts:
            posts[group_id] = GroupedMessages(group_id, post.id, post.date)
        posts[group_id].messages.append(post)
    if len(posts) == 0:
        logging.warning(f"No posts found at the target date: {target_date}")
    return list(posts.values())

def can_be_reposted(post: tg.Message) -> bool:
    if post.post_author == ignored_author:
        logging.info(f"Skipping because it's from an ignored author")
        return False
    if post.media == None:
        logging.info(f"Skipping because it doesn't contain media")
        return False
    if not is_supported_media(post.media):
        logging.info(f"Skipping because media is not supported: {post.media.to_dict()}")
        return False
    if isinstance(post.media, tg.MessageMediaDocument) and isinstance(post.media.document, tg.Document) and post.media.document.mime_type == "image/webp":
        logging.info(f"Skipping because it's a sticker")
        return False
    if post.reply_to != None:
        logging.info(f"Ignoring reply_to post ({post.id})")
        return False
    return True

# The first parameter is the .session file name (absolute paths allowed)
with user:
    user.loop.run_until_complete(main())
