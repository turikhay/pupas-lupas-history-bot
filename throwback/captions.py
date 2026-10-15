import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import tzinfo

from .model import Entity, EntityKind, Group, Post
from .selection import THROWBACK_HASHTAG

# Bots' media captions are limited to 1024 characters, which Telegram counts in UTF-16 code units
CAPTION_LIMIT = 1024
# How far back truncation may go to cut at a space instead of in the middle of a word
WORD_BOUNDARY_REACH = 30
SEPARATOR = "\n\n"
ELLIPSIS = "…"

# A letter is required: "#1" is a number, not a hashtag. "#tag@channel" is a channel-scoped hashtag
_hashtag = re.compile(r"(?<![\w#])#(?=\w*[^\W\d_])\w+(?:@\w+)?")


@dataclass(frozen=True)
class Caption:
    text: str
    entities: tuple[Entity, ...] = ()


def utf16_len(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def merge(posts: Iterable[Post]) -> tuple[str, tuple[Entity, ...]]:
    """Joins the captions of album items, like Group.text, keeping their formatting."""
    text = ""
    entities: list[Entity] = []
    for post in posts:
        if not post.text:
            continue
        if text:
            text += "\n"
        shift = utf16_len(text)
        entities += [replace(entity, offset=entity.offset + shift) for entity in post.entities]
        text += post.text
    return text, tuple(entities)


def has_text_besides_hashtags(text: str) -> bool:
    # Emoji count as text, the spaces and commas between hashtags don't
    return any(not ch.isspace() and not unicodedata.category(ch).startswith("P") for ch in _hashtag.sub("", text))


def truncate(text: str, entities: Sequence[Entity], limit: int) -> tuple[str, tuple[Entity, ...]]:
    """Fits the text into limit UTF-16 code units, ending it with an ellipsis if it had to be cut."""
    if utf16_len(text) <= limit:
        return text, tuple(entities)
    budget = limit - utf16_len(ELLIPSIS)
    cut = used = 0
    for ch in text:
        used += utf16_len(ch)
        if used > budget:
            break
        cut += 1
    space = max((i for i in range(max(cut - WORD_BOUNDARY_REACH, 0), cut) if text[i].isspace()), default=None)
    if space is not None:
        cut = space
    # Don't leave whitespace before the ellipsis
    while cut > 0 and text[cut - 1].isspace():
        cut -= 1
    end = utf16_len(text[:cut])
    clipped = tuple(replace(e, length=min(e.offset + e.length, end) - e.offset) for e in entities if e.offset < end)
    return text[:cut] + ELLIPSIS, clipped


def build_caption(group: Group, username: str | None, tz: tzinfo, limit: int = CAPTION_LIMIT) -> Caption:
    """The original caption as is, unless it's nothing but hashtags, and a link to the original with its year."""
    # The year in the channel's timezone: a post at 00:30 on Jan 1 is not from the previous year
    year = str(group.first.date.astimezone(tz).year)
    footer = f"{year} {THROWBACK_HASHTAG}"
    link = Entity(EntityKind.TEXT_URL, 0, utf16_len(year), url=f"https://t.me/{username}/{group.first.id}")
    text, entities = merge(group.posts)
    if not has_text_besides_hashtags(text):
        return Caption(footer, (link,))
    text, entities = truncate(text, entities, limit - utf16_len(SEPARATOR + footer))
    return Caption(text + SEPARATOR + footer, (*entities, replace(link, offset=utf16_len(text + SEPARATOR))))
