import logging
from telethon import types as tg

from message import GroupedMessages
from supported_media import is_supported_media

def can_be_reposted(group: GroupedMessages, ignored_author: str, is_wednesday: bool) -> bool:
    # Albums are reposted as a whole, so a single bad item rejects the group
    for post in group.messages:
        if post.post_author == ignored_author:
            logging.info(f"Skipping {group}: it's from an ignored author")
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
    if text and not is_wednesday:
        msgl = text.lower()
        mentions_wednesday = any(
            frag in msgl for frag in (
                "wednesday",
                "сред", # сред(-а,-ы,-у,...)
            )
        )
        if mentions_wednesday:
            logging.info(f"Skipping {group}: it's not Wednesday, but the post mentions it 😡")
            return False
    return True
