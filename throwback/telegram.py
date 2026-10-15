import logging
import tempfile
from datetime import date, timedelta, tzinfo

from telethon import TelegramClient
from telethon import types as tg

from .dates import start_of_day
from .model import Group, MediaKind, Post


def media_kind(media: tg.TypeMessageMedia | None) -> MediaKind:
    if media is None:
        return MediaKind.NONE
    if isinstance(media, tg.MessageMediaPhoto):
        return MediaKind.PHOTO
    if not isinstance(media, tg.MessageMediaDocument) or not isinstance(media.document, tg.Document):
        return MediaKind.UNSUPPORTED
    attributes = media.document.attributes
    if media.document.mime_type == "image/webp" or any(isinstance(a, tg.DocumentAttributeSticker) for a in attributes):
        return MediaKind.STICKER
    if any(isinstance(a, tg.DocumentAttributeAnimated) for a in attributes):
        return MediaKind.GIF
    for attribute in attributes:
        if isinstance(attribute, tg.DocumentAttributeVideo):
            return MediaKind.VIDEO_NOTE if attribute.round_message else MediaKind.VIDEO
        if isinstance(attribute, tg.DocumentAttributeAudio):
            return MediaKind.VOICE if attribute.voice else MediaKind.AUDIO
    return MediaKind.DOCUMENT


def emoji_reactions(reactions: tg.MessageReactions | None) -> dict[str, int]:
    if reactions is None:
        return {}
    return {r.reaction.emoticon: r.count for r in reactions.results if isinstance(r.reaction, tg.ReactionEmoji)}


def to_post(message: tg.Message) -> Post:
    assert message.date is not None
    return Post(
        id=message.id,
        date=message.date,
        media=media_kind(message.media),
        text=message.message or "",
        grouped_id=message.grouped_id,
        author=message.post_author,
        reply_to=message.reply_to.reply_to_msg_id if isinstance(message.reply_to, tg.MessageReplyHeader) else None,
        reactions=emoji_reactions(message.reactions),
    )


class Channel:
    """Reads the channel history with the user account and reposts with the bot."""

    def __init__(self, user: TelegramClient, bot: TelegramClient, channel: tg.Channel, target, tz: tzinfo):
        self._user = user
        self._bot = bot
        self._channel = channel
        self._target = target
        self._tz = tz
        # Telethon messages behind the posts handed out, needed to download their media
        self._messages: dict[int, tg.Message] = {}

    @property
    def username(self) -> str | None:
        return self._channel.username

    async def fetch_day(self, day: date) -> list[Post]:
        day_start = start_of_day(day, self._tz)
        day_end = day_start + timedelta(days=1)
        # The last media post before the day, to iterate forward from it
        anchor = await self._user.get_messages(
            self._channel, limit=1, offset_date=day_start, filter=tg.InputMessagesFilterPhotoVideo
        )
        if not isinstance(anchor, list) or not anchor:
            logging.warning(f"get_messages returned empty list for {self._channel.id}")
            return []
        posts: list[Post] = []
        async for message in self._user.iter_messages(self._channel, reverse=True, offset_id=anchor[0].id, limit=100):
            if not isinstance(message, tg.Message):
                logging.info(f"Skipping {message.id}: it's not a message ({type(message).__name__})")
                continue
            assert message.date is not None
            if message.date < day_start:
                continue
            if message.date >= day_end:
                break
            self._messages[message.id] = message
            posts.append(to_post(message))
        if not posts:
            logging.warning(f"No posts found at the target date: {day}")
        return posts

    async def repost(self, group: Group, caption: str) -> None:
        messages = [self._messages[post.id] for post in group.posts]
        with tempfile.TemporaryDirectory(prefix="throwback-") as tmp:
            files: list[str] = []
            for message in messages:
                path = await self._user.download_media(message, file=tmp)
                if not isinstance(path, str):
                    raise RuntimeError(f"Couldn't download the media of message {message.id}")
                files.append(path)
            await self._bot.send_message(
                self._target,
                message=caption,
                file=files,
                reply_to=group.reply_to,  # type: ignore[arg-type]
                silent=True,
            )
