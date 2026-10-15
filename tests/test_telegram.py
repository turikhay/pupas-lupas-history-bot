import asyncio
from datetime import UTC, datetime
from typing import Any, cast

import pytest
from telethon import TelegramClient, functions
from telethon import types as tg

from tests.factories import group, post
from throwback.captions import Caption
from throwback.model import Entity, EntityKind, Group, MediaKind
from throwback.telegram import (
    BotPublisher,
    custom_emoji_ids,
    emoji_reactions,
    media_kind,
    paid_stars,
    resolve_custom_emoji,
    to_entities,
    to_post,
    to_telethon_entity,
)

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
    publisher = BotPublisher(
        bot=cast(TelegramClient, bot),
        bot_channel=tg.InputPeerChannel(1, 0),
        target=tg.InputPeerChat(2),
        keep_replies=keep_replies,
    )
    asyncio.run(publisher.repost(group, Caption("caption", (Entity(EntityKind.BOLD, 0, 3),))))


def test_repost_sends_the_bots_own_copies_of_an_album_by_reference() -> None:
    bot = FakeBot({11: photo_message(11), 12: photo_message(12)})
    repost(bot, group(post(11, grouped_id=9, reply_to=3), post(12, grouped_id=9)))
    assert bot.requested == [11, 12]
    [(target, media, kwargs)] = bot.sent
    assert target == tg.InputPeerChat(2)
    assert media == [bot.messages[11].media, bot.messages[12].media]
    assert kwargs == {
        "caption": "caption",
        "formatting_entities": [tg.MessageEntityBold(0, 3)],
        "parse_mode": None,
        "reply_to": 3,
        "silent": True,
    }


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


def test_to_entities_keeps_formatting_only() -> None:
    entities = to_entities(
        [
            tg.MessageEntityBold(0, 3),
            tg.MessageEntityTextUrl(4, 5, url="https://example.com"),
            tg.MessageEntityPre(10, 2, language="py"),
            tg.MessageEntityHashtag(13, 4),
            tg.MessageEntityUrl(18, 10),
            tg.MessageEntityMention(29, 5),
            tg.MessageEntityCustomEmoji(35, 2, document_id=7),
        ]
    )
    assert entities == (
        Entity(EntityKind.BOLD, 0, 3),
        Entity(EntityKind.TEXT_URL, 4, 5, url="https://example.com"),
        Entity(EntityKind.PRE, 10, 2, language="py"),
    )
    assert to_entities(None) == ()


@pytest.mark.parametrize("kind", list(EntityKind))
def test_entities_round_trip(kind: EntityKind) -> None:
    entity = Entity(
        kind,
        3,
        4,
        url="https://example.com" if kind is EntityKind.TEXT_URL else None,
        language="py" if kind is EntityKind.PRE else None,
    )
    assert to_entities([to_telethon_entity(entity)]) == (entity,)


SMILE_ID, HEART_ID, UNKNOWN_ID = 101, 102, 103


def reactions(*results: tuple[tg.TypeReaction, int]) -> tg.MessageReactions:
    return tg.MessageReactions(results=[tg.ReactionCount(reaction=r, count=n) for r, n in results])


def test_custom_emoji_count_as_the_emoji_they_stand_for() -> None:
    counts = emoji_reactions(
        reactions(
            (tg.ReactionEmoji("❤"), 2),
            (tg.ReactionCustomEmoji(HEART_ID), 3),
            (tg.ReactionCustomEmoji(SMILE_ID), 1),
            (tg.ReactionCustomEmoji(UNKNOWN_ID), 7),
            (tg.ReactionPaid(), 5),
        ),
        {HEART_ID: "❤️", SMILE_ID: "😀"},
    )
    assert counts == {"❤": 5, "😀": 1}


def test_paid_stars() -> None:
    assert paid_stars(reactions((tg.ReactionEmoji("🔥"), 2), (tg.ReactionPaid(), 5))) == 5
    assert paid_stars(None) == 0


def test_to_post_counts_custom_emoji_and_stars() -> None:
    message = tg.Message(
        id=1,
        peer_id=tg.PeerChannel(1),
        date=DATE,
        message="",
        reactions=reactions((tg.ReactionCustomEmoji(SMILE_ID), 2), (tg.ReactionPaid(), 3)),
    )
    post = to_post(message, {SMILE_ID: "😀"})
    assert (post.reactions, post.stars) == ({"😀": 2}, 3)


def custom_emoji_document(id: int, alt: str) -> tg.Document:
    attribute = tg.DocumentAttributeCustomEmoji(alt=alt, stickerset=tg.InputStickerSetEmpty())
    return tg.Document(
        id=id,
        access_hash=0,
        file_reference=b"",
        date=DATE,
        mime_type="image/webp",
        size=1,
        dc_id=1,
        attributes=[attribute],
    )


class FakeUser:
    def __init__(self, alts: dict[int, str]):
        self.alts = alts
        self.asked: list[list[int]] = []

    async def __call__(self, request: functions.messages.GetCustomEmojiDocumentsRequest) -> list[tg.Document]:
        self.asked.append(request.document_id)
        return [custom_emoji_document(id, self.alts[id]) for id in request.document_id if id in self.alts]


def test_resolve_custom_emoji_asks_only_about_new_ones() -> None:
    user = FakeUser({SMILE_ID: "😀", HEART_ID: "❤️"})
    known = {SMILE_ID: "😀"}
    resolved = asyncio.run(resolve_custom_emoji(cast(TelegramClient, user), [SMILE_ID, HEART_ID], known))
    assert resolved == {SMILE_ID: "😀", HEART_ID: "❤️"}
    assert user.asked == [[HEART_ID]]
    asyncio.run(resolve_custom_emoji(cast(TelegramClient, user), [SMILE_ID, HEART_ID], known))
    assert user.asked == [[HEART_ID]]


def test_custom_emoji_ids() -> None:
    messages = [
        tg.Message(
            id=1,
            peer_id=tg.PeerChannel(1),
            date=DATE,
            message="",
            reactions=reactions((tg.ReactionCustomEmoji(SMILE_ID), 1)),
        ),
        tg.Message(
            id=2, peer_id=tg.PeerChannel(1), date=DATE, message="", reactions=reactions((tg.ReactionEmoji("🔥"), 1))
        ),
        tg.Message(id=3, peer_id=tg.PeerChannel(1), date=DATE, message=""),
    ]
    assert custom_emoji_ids(messages) == {SMILE_ID}
