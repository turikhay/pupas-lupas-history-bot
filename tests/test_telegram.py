from datetime import UTC, datetime

import pytest
from telethon import types as tg

from throwback.model import MediaKind
from throwback.telegram import media_kind, to_post

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
