from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class MediaKind(StrEnum):
    NONE = "none"
    PHOTO = "photo"
    VIDEO = "video"
    GIF = "gif"
    VIDEO_NOTE = "video_note"
    VOICE = "voice"
    AUDIO = "audio"
    STICKER = "sticker"
    DOCUMENT = "document"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True)
class Post:
    """A channel message, detached from Telethon so that the selection logic can be tested offline."""

    id: int
    date: datetime  # aware, as Telegram reports it (UTC)
    media: MediaKind
    text: str = ""
    grouped_id: int | None = None
    author: str | None = None
    reply_to: int | None = None
    # Emoji reaction counts by emoticon; custom emoji and paid reactions are not counted
    reactions: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class Group:
    """A single post or an album; it is filtered, ranked and reposted as a whole."""

    posts: tuple[Post, ...]

    @property
    def first(self) -> Post:
        return self.posts[0]

    @property
    def key(self) -> int:
        # What memery stores: the album's grouped_id or the message id
        return self.first.grouped_id if self.first.grouped_id is not None else self.first.id

    @property
    def text(self) -> str:
        # An album usually has a caption on one of its items only
        return "\n".join(post.text for post in self.posts if post.text)

    @property
    def reply_to(self) -> int | None:
        return self.first.reply_to

    def __str__(self) -> str:
        return f"Group{{key={self.key},msg_id={self.first.id},date={self.first.date},messages_count={len(self.posts)}}}"
