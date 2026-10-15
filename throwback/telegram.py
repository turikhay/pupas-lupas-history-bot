import logging
from collections.abc import Iterable, Mapping
from datetime import date, timedelta, tzinfo

from telethon import TelegramClient, functions
from telethon import types as tg

from .captions import Caption
from .dates import start_of_day
from .model import Entity, EntityKind, Group, MediaKind, Post

_ENTITY_TYPES: dict[EntityKind, type] = {
    EntityKind.BOLD: tg.MessageEntityBold,
    EntityKind.ITALIC: tg.MessageEntityItalic,
    EntityKind.UNDERLINE: tg.MessageEntityUnderline,
    EntityKind.STRIKE: tg.MessageEntityStrike,
    EntityKind.SPOILER: tg.MessageEntitySpoiler,
    EntityKind.CODE: tg.MessageEntityCode,
    EntityKind.PRE: tg.MessageEntityPre,
    EntityKind.TEXT_URL: tg.MessageEntityTextUrl,
    EntityKind.BLOCKQUOTE: tg.MessageEntityBlockquote,
}
_ENTITY_KINDS = {telethon_type: kind for kind, telethon_type in _ENTITY_TYPES.items()}


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


def emoji_reactions(reactions: tg.MessageReactions | None, custom_emoji: Mapping[int, str]) -> dict[str, int]:
    """Reaction counts by emoticon; custom emoji count as the emoji they stand for (custom_emoji: id → emoji)."""
    counts: dict[str, int] = {}
    for r in reactions.results if reactions else ():
        if isinstance(r.reaction, tg.ReactionEmoji):
            emoticon = r.reaction.emoticon
        elif isinstance(r.reaction, tg.ReactionCustomEmoji) and r.reaction.document_id in custom_emoji:
            emoticon = custom_emoji[r.reaction.document_id]
        else:
            continue
        # "❤️" and "❤" are the same reaction, with and without the emoji presentation selector
        emoticon = emoticon.replace("\ufe0f", "")
        counts[emoticon] = counts.get(emoticon, 0) + r.count
    return counts


def paid_stars(reactions: tg.MessageReactions | None) -> int:
    return sum(r.count for r in reactions.results if isinstance(r.reaction, tg.ReactionPaid)) if reactions else 0


def custom_emoji_ids(messages: Iterable[tg.Message]) -> set[int]:
    return {
        r.reaction.document_id
        for message in messages
        if message.reactions
        for r in message.reactions.results
        if isinstance(r.reaction, tg.ReactionCustomEmoji)
    }


async def resolve_custom_emoji(client: TelegramClient, ids: Iterable[int], known: dict[int, str]) -> dict[int, str]:
    """Adds the emoji that the custom emoji stand for to known, asking Telegram only about the new ones."""
    missing = [id for id in ids if id not in known]
    if missing:
        documents = await client(functions.messages.GetCustomEmojiDocumentsRequest(document_id=missing))
        for document in documents:
            for attribute in getattr(document, "attributes", ()):
                if isinstance(attribute, tg.DocumentAttributeCustomEmoji):
                    known[document.id] = attribute.alt
    return known


def to_entities(entities: list[tg.TypeMessageEntity] | None) -> tuple[Entity, ...]:
    # Links, mentions and hashtags are detected by Telegram again; custom emoji fall back to their plain emoji
    return tuple(
        Entity(
            kind=_ENTITY_KINDS[type(entity)],
            offset=entity.offset,
            length=entity.length,
            url=entity.url if isinstance(entity, tg.MessageEntityTextUrl) else None,
            language=entity.language if isinstance(entity, tg.MessageEntityPre) else None,
        )
        for entity in entities or ()
        if type(entity) in _ENTITY_KINDS
    )


def to_telethon_entity(entity: Entity) -> tg.TypeMessageEntity:
    if entity.kind is EntityKind.TEXT_URL:
        return tg.MessageEntityTextUrl(entity.offset, entity.length, url=entity.url or "")
    if entity.kind is EntityKind.PRE:
        return tg.MessageEntityPre(entity.offset, entity.length, language=entity.language or "")
    return _ENTITY_TYPES[entity.kind](entity.offset, entity.length)


def to_post(message: tg.Message, custom_emoji: Mapping[int, str] | None = None) -> Post:
    assert message.date is not None
    return Post(
        id=message.id,
        date=message.date,
        media=media_kind(message.media),
        text=message.message or "",
        entities=to_entities(message.entities),
        grouped_id=message.grouped_id,
        author=message.post_author,
        reply_to=message.reply_to.reply_to_msg_id if isinstance(message.reply_to, tg.MessageReplyHeader) else None,
        reactions=emoji_reactions(message.reactions, custom_emoji or {}),
        stars=paid_stars(message.reactions),
    )


class ChannelHistory:
    """Reads the channel with the user account: unlike the bot, it can read history and see reactions."""

    def __init__(self, user: TelegramClient, channel: tg.Channel, tz: tzinfo):
        self._user = user
        self._channel = channel
        self._tz = tz
        # Custom emoji id → the emoji it stands for; a channel only allows a few, so they're asked about once
        self._custom_emoji: dict[int, str] = {}

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
        messages: list[tg.Message] = []
        async for message in self._user.iter_messages(self._channel, reverse=True, offset_id=anchor[0].id, limit=100):
            if not isinstance(message, tg.Message):
                logging.info(f"Skipping {message.id}: it's not a message ({type(message).__name__})")
                continue
            assert message.date is not None
            if message.date < day_start:
                continue
            if message.date >= day_end:
                break
            messages.append(message)
        if not messages:
            logging.warning(f"No posts found at the target date: {day}")
        await resolve_custom_emoji(self._user, custom_emoji_ids(messages), self._custom_emoji)
        return [to_post(message, self._custom_emoji) for message in messages]


class BotPublisher:
    """Reposts with the bot by reference to the original media, so nothing is downloaded or re-encoded."""

    def __init__(
        self,
        bot: TelegramClient,
        bot_channel: tg.TypeInputPeer,
        target: tg.TypeInputPeer,
        keep_replies: bool = True,
    ):
        self._bot = bot
        self._bot_channel = bot_channel
        self._target = target
        # Reply ids point into the channel, so they're meaningless anywhere else
        self._keep_replies = keep_replies

    async def repost(self, group: Group, caption: Caption) -> None:
        # File references are bound to the account that fetched the message, so the bot fetches its own copies
        messages = await self._bot.get_messages(self._bot_channel, ids=[post.id for post in group.posts])
        assert isinstance(messages, list)
        media = [message.media for message in messages if message is not None and message.media is not None]
        if len(media) != len(group.posts):
            raise RuntimeError(f"Some messages of {group} are gone or have no media")
        await self._bot.send_file(
            self._target,
            media if len(media) > 1 else media[0],
            caption=caption.text,
            # Ready-made entities, so that the original text isn't parsed as markdown
            formatting_entities=[to_telethon_entity(entity) for entity in caption.entities],
            parse_mode=None,
            reply_to=group.reply_to if self._keep_replies else None,  # type: ignore[arg-type]
            silent=True,
        )
