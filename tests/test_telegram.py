import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from telethon import TelegramClient
from telethon import types as tg

from tests.factories import group, post
from throwback.model import Group, MediaKind
from throwback.telegram import Channel, media_kind, to_post

DATE = datetime(2019, 10, 15, 12, tzinfo=UTC)


def document(mime: str, *attributes) -> tg.MessageMediaDocument:
    return tg.MessageMediaDocument(
        document=tg.Document(
            id=1,
            access_hash=0,
            file_reference=b"",
            date=DATE,
            mime_type=mime,
            size=1,
            dc_id=1,
            attributes=list(attributes),
        )
    )


VIDEO = tg.DocumentAttributeVideo(duration=3, w=640, h=480)
ROUND_VIDEO = tg.DocumentAttributeVideo(duration=3, w=1, h=1, round_message=True)
STICKER = tg.DocumentAttributeSticker(alt="", stickerset=tg.InputStickerSetEmpty())


@pytest.mark.parametrize(
    ("media", "expected"),
    [
        (None, MediaKind.NONE),
        (tg.MessageMediaPhoto(photo=tg.PhotoEmpty(id=1)), MediaKind.PHOTO),
        (document("image/webp"), MediaKind.STICKER),
        (document("application/x-tgsticker", STICKER), MediaKind.STICKER),
        (document("video/mp4", VIDEO, tg.DocumentAttributeAnimated()), MediaKind.GIF),
        (document("video/mp4", VIDEO), MediaKind.VIDEO),
        (document("video/mp4", ROUND_VIDEO), MediaKind.VIDEO_NOTE),
        (document("audio/ogg", tg.DocumentAttributeAudio(duration=3, voice=True)), MediaKind.VOICE),
        (document("audio/mpeg", tg.DocumentAttributeAudio(duration=3)), MediaKind.AUDIO),
        (document("application/pdf"), MediaKind.DOCUMENT),
        (tg.MessageMediaDocument(document=tg.DocumentEmpty(id=1)), MediaKind.UNSUPPORTED),
        (tg.MessageMediaWebPage(webpage=tg.WebPageEmpty(id=1)), MediaKind.UNSUPPORTED),
    ],
    ids=lambda v: v if isinstance(v, MediaKind) else None,
)
def test_media_kind(media, expected: MediaKind) -> None:
    assert media_kind(media) is expected


def test_to_post() -> None:
    message = tg.Message(
        id=42,
        peer_id=tg.PeerChannel(1),
        date=DATE,
        message="caption",
        media=tg.MessageMediaPhoto(photo=tg.PhotoEmpty(id=1)),
        grouped_id=9,
        post_author="Вася",
        reply_to=tg.MessageReplyHeader(reply_to_msg_id=40),
        reactions=tg.MessageReactions(
            results=[
                tg.ReactionCount(reaction=tg.ReactionEmoji("🔥"), count=3),
                tg.ReactionCount(reaction=tg.ReactionCustomEmoji(document_id=7), count=5),
            ]
        ),
    )
    post = to_post(message)
    assert (post.id, post.date, post.media, post.text) == (42, DATE, MediaKind.PHOTO, "caption")
    assert (post.grouped_id, post.author, post.reply_to) == (9, "Вася", 40)
    assert post.reactions == {"🔥": 3}


def test_to_post_without_caption_and_reactions() -> None:
    post = to_post(tg.Message(id=1, peer_id=tg.PeerChannel(1), date=DATE, message=""))
    assert (post.text, post.media, post.reply_to, post.reactions) == ("", MediaKind.NONE, None, {})


class FakeBot:
    def __init__(self, messages: dict[int, tg.Message]):
        self.messages = messages
        self.requested: list[int] = []
        self.sent: list[tuple[Any, Any, dict[str, Any]]] = []

    async def get_messages(self, entity: Any, ids: list[int]) -> list[tg.Message | None]:
        self.requested += ids
        return [self.messages.get(id) for id in ids]

    async def send_file(self, entity: Any, file: Any, **kwargs: Any) -> None:
        self.sent.append((entity, file, kwargs))


def photo_message(id: int) -> tg.Message:
    return tg.Message(
        id=id, peer_id=tg.PeerChannel(1), date=DATE, message="", media=tg.MessageMediaPhoto(photo=tg.PhotoEmpty(id=id))
    )


def repost(bot: FakeBot, group: Group, keep_replies: bool = True) -> None:
    channel = Channel(
        user=cast(TelegramClient, None),
        bot=cast(TelegramClient, bot),
        channel=cast(tg.Channel, None),
        bot_channel=tg.InputPeerChannel(1, 0),
        target=tg.InputPeerChat(2),
        tz=UTC,
        keep_replies=keep_replies,
    )
    asyncio.run(channel.repost(group, "caption"))


def test_repost_sends_the_bots_own_copies_of_an_album_by_reference() -> None:
    bot = FakeBot({11: photo_message(11), 12: photo_message(12)})
    repost(bot, group(post(11, grouped_id=9, reply_to=3), post(12, grouped_id=9)))
    assert bot.requested == [11, 12]
    [(target, media, kwargs)] = bot.sent
    assert target == tg.InputPeerChat(2)
    assert media == [bot.messages[11].media, bot.messages[12].media]
    assert kwargs == {"caption": "caption", "reply_to": 3, "silent": True}


def test_repost_sends_a_single_post_as_one_media() -> None:
    bot = FakeBot({11: photo_message(11)})
    repost(bot, group(post(11)))
    assert bot.sent[0][1] == bot.messages[11].media


def test_repost_drops_replies_outside_the_channel() -> None:
    bot = FakeBot({11: photo_message(11)})
    repost(bot, group(post(11, reply_to=3)), keep_replies=False)
    assert bot.sent[0][2]["reply_to"] is None


def test_repost_fails_when_a_message_is_gone() -> None:
    bot = FakeBot({11: photo_message(11)})
    with pytest.raises(RuntimeError, match="gone"):
        repost(bot, group(post(11, grouped_id=9), post(12, grouped_id=9)))
    assert bot.sent == []
