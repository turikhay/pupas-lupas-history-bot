import logging
import random
import re
from collections.abc import Collection, Iterable, Sequence

from .model import Group, MediaKind, Post

# Every repost is captioned with it, so it also marks the bot's own posts
THROWBACK_HASHTAG = "#MemeThrowback"

# Whole words only: a bare "сред" prefix also matches "среди", "средство", "средний"
wednesday_pattern = re.compile(
    r"\b(wednesdays?|сред(а|у|ы|е|ой|ою|ам|ами|ах)?)\b",
    re.IGNORECASE,
)

# Memes are pictures and videos: voice messages, audio, round videos and files aren't reposted
REPOSTABLE_MEDIA = frozenset({MediaKind.PHOTO, MediaKind.VIDEO, MediaKind.GIF})

NEGATIVE_EMOTICONS = frozenset(("👎", "💩", "🥱", "🤔"))
# A paid star is worth this many ordinary reactions
STAR_WEIGHT = 10


def group_posts(posts: Iterable[Post]) -> list[Group]:
    """Collects album items together, keeping the order in which groups first appear."""
    groups: dict[int, list[Post]] = {}
    for post in posts:
        groups.setdefault(post.grouped_id if post.grouped_id is not None else post.id, []).append(post)
    return [Group(tuple(items)) for items in groups.values()]


def can_be_reposted(group: Group, ignored_authors: Collection[str], is_wednesday: bool) -> bool:
    # Albums are reposted as a whole, so a single bad item rejects the group
    for post in group.posts:
        if post.author in ignored_authors:
            logging.info(f"Skipping {group}: it's from an ignored author ({post.author})")
            return False
        if post.media not in REPOSTABLE_MEDIA:
            logging.info(f"Skipping {group}: message {post.id} has {post.media} media")
            return False
    text = group.text
    if THROWBACK_HASHTAG.lower() in text.lower():
        # Signatures can't be trusted alone: they change with the bot's name
        logging.info(f"Skipping {group}: it's our own repost")
        return False
    if not is_wednesday and wednesday_pattern.search(text):
        logging.info(f"Skipping {group}: it's not Wednesday, but the post mentions it 😡")
        return False
    return True


def score(group: Group) -> int:
    post = group.first
    reactions = sum(-count if emoticon in NEGATIVE_EMOTICONS else count for emoticon, count in post.reactions.items())
    return reactions + STAR_WEIGHT * post.stars


def rank(groups: Sequence[Group], rng: random.Random) -> list[Group]:
    """Best reactions first, random within a tier, negatively rated groups dropped; random order without reactions."""
    scores = [score(group) for group in groups]
    if all(s == 0 for s in scores):
        logging.info("Random sorted")
        shuffled = list(groups)
        rng.shuffle(shuffled)
        return shuffled
    logging.info("Sorted by best")
    evaluated = [(group, s + rng.random() / 2) for group, s in zip(groups, scores, strict=True) if s >= 0]
    evaluated.sort(key=lambda e: e[1], reverse=True)
    return [group for group, _ in evaluated]
