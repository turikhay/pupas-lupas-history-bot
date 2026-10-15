import logging
import re
from collections.abc import Collection
from telethon import types as tg

from message import GroupedMessages
from supported_media import is_supported_media

# Every repost is captioned with it, so it also marks the bot's own posts
THROWBACK_HASHTAG = "#MemeThrowback"

# Whole words only: a bare "сред" prefix also matches "среди", "средство", "средний"
wednesday_pattern = re.compile(
    r"\b(wednesdays?|сред(а|у|ы|е|ой|ою|ам|ами|ах)?)\b",
    re.IGNORECASE,
)

def can_be_reposted(group: GroupedMessages, ignored_authors: Collection[str], is_wednesday: bool) -> bool:
    # Albums are reposted as a whole, so a single bad item rejects the group
    for post in group.messages:
        if post.post_author in ignored_authors:
            logging.info(f"Skipping {group}: it's from an ignored author ({post.post_author})")
            return False
        if post.media == None:
            logging.info(f"Skipping {group}: message {post.id} doesn't contain media")
            return False
        if not is_supported_media(post.media):
            logging.info(f"Skipping {group}: media is not supported: {post.media.to_dict()}")
            return False
        if isinstance(post.media, tg.MessageMediaDocument) and isinstance(post.media.document, tg.Document) and post.media.document.mime_type == "image/webp":
            logging.info(f"Skipping {group}: message {post.id} is a sticker")
            return False
    text = group.text()
    if THROWBACK_HASHTAG.lower() in text.lower():
        # Signatures can't be trusted alone: they change with the bot's name
        logging.info(f"Skipping {group}: it's our own repost")
        return False
    if not is_wednesday and wednesday_pattern.search(text):
        logging.info(f"Skipping {group}: it's not Wednesday, but the post mentions it 😡")
        return False
    return True
