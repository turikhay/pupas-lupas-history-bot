import random

import pytest

from tests.factories import group, post
from throwback.model import Group, MediaKind
from throwback.selection import can_be_reposted, group_posts, rank, score

AUTHORS = frozenset({"День в истории", "Альцгеймер"})


def test_group_posts_collects_albums_in_order() -> None:
    posts = [post(1), post(2, grouped_id=9), post(3, grouped_id=9), post(4)]
    assert [[p.id for p in g.posts] for g in group_posts(posts)] == [[1], [2, 3], [4]]


def test_group_key_is_grouped_id_for_albums_and_id_otherwise() -> None:
    assert group(post(2, grouped_id=9), post(3, grouped_id=9)).key == 9
    assert group(post(5)).key == 5


@pytest.mark.parametrize(
    ("g", "is_wednesday", "expected"),
    [
        (group(post(1)), False, True),
        (group(post(1, grouped_id=9), post(2, text="среда, мои чуваки", grouped_id=9)), False, False),
        (group(post(1, grouped_id=9), post(2, text="среда, мои чуваки", grouped_id=9)), True, True),
        (group(post(1, grouped_id=9), post(2, MediaKind.STICKER, grouped_id=9)), False, False),
        (group(post(1, MediaKind.NONE, text="просто текст")), False, False),
        (group(post(1, MediaKind.UNSUPPORTED)), False, False),
        (group(post(1, MediaKind.GIF)), False, True),
        (group(post(1, MediaKind.VIDEO)), False, True),
        (group(post(1, author="Альцгеймер")), False, False),
        (group(post(1, author="День в истории")), False, False),
        (group(post(1, author="Вася")), False, True),
    ],
    ids=[
        "photo",
        "album-wednesday-caption-on-2nd-item",
        "same-album-on-wednesday",
        "album-with-sticker",
        "text-only",
        "unsupported-media",
        "gif",
        "video",
        "current-bot-name",
        "old-bot-name",
        "other-author",
    ],
)
def test_can_be_reposted(g: Group, is_wednesday: bool, expected: bool) -> None:
    assert can_be_reposted(g, AUTHORS, is_wednesday) is expected


@pytest.mark.parametrize(
    "caption",
    ["[2019](https://t.me/x/1) #MemeThrowback", "#memethrowback"],
)
def test_own_reposts_are_rejected_even_without_signature(caption: str) -> None:
    album = group(post(1, text=caption, grouped_id=9), post(2, grouped_id=9))
    assert not can_be_reposted(album, frozenset(), is_wednesday=False)


@pytest.mark.parametrize(
    ("text", "mentions_wednesday"),
    [
        ("среди нас предатель", False),
        ("лучшее средство от скуки", False),
        ("средний класс", False),
        ("посреди ночи", False),
        ("Средневековье было лучше", False),
        ("жду среду", True),
        ("СРЕДОЙ", True),
        ("нет больше сред", True),
        ("по средам", True),
        ("I hate Wednesdays", True),
        ("It is Wednesday my dudes", True),
    ],
)
def test_wednesday_is_matched_as_a_whole_word(text: str, mentions_wednesday: bool) -> None:
    g = group(post(1, text=text))
    assert can_be_reposted(g, frozenset(), is_wednesday=False) is not mentions_wednesday
    assert can_be_reposted(g, frozenset(), is_wednesday=True)


def test_score_counts_negative_emoticons_against() -> None:
    assert score(group(post(1, reactions={"🔥": 5, "👎": 2, "🤔": 1}))) == 2


def test_score_uses_the_first_album_item() -> None:
    assert score(group(post(1, grouped_id=9), post(2, grouped_id=9, reactions={"🔥": 5}))) == 0


def test_rank_puts_best_first_and_drops_negative() -> None:
    good, better, bad, plain = (
        group(post(1, reactions={"🔥": 1})),
        group(post(2, reactions={"🔥": 3})),
        group(post(3, reactions={"💩": 2})),
        group(post(4)),
    )
    for seed in range(20):
        assert rank([good, better, bad, plain], random.Random(seed)) == [better, good, plain]


def test_rank_shuffles_without_reactions() -> None:
    groups = [group(post(i)) for i in range(10)]
    orders = {tuple(g.key for g in rank(groups, random.Random(seed))) for seed in range(5)}
    assert all(sorted(order) == list(range(10)) for order in orders)
    assert len(orders) > 1
