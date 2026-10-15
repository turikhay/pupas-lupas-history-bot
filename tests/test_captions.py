from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from tests.factories import group, post
from throwback.captions import (
    CAPTION_LIMIT,
    Caption,
    build_caption,
    has_text_besides_hashtags,
    merge,
    truncate,
    utf16_len,
)
from throwback.model import Entity, EntityKind

TZ = ZoneInfo("Asia/Yekaterinburg")
B = EntityKind.BOLD
FOOTER = "2019 #MemeThrowback"


def link(offset: int, id: int = 1, year: str = "2019") -> Entity:
    return Entity(EntityKind.TEXT_URL, offset, len(year), url=f"https://t.me/pupaslupas/{id}")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#мем #юмор", False),
        ("#shrek #mashup", False),
        ("#мем, #юмор.", False),
        ("#мем\n#юмор", False),
        ("#тег@pupaslupas", False),
        ("", False),
        (" \n", False),
        ("Мем дня #мем #юмор", True),
        ("#мем Мем дня", True),
        ("Skyrim #gaming", True),
        ("#мем 😂", True),
        ("C# #код", True),
        ("#1 место", True),
    ],
)
def test_has_text_besides_hashtags(text: str, expected: bool) -> None:
    assert has_text_besides_hashtags(text) is expected


def test_merge_joins_album_captions_and_shifts_entities() -> None:
    posts = [
        post(1, text="один", entities=(Entity(B, 0, 4),)),
        post(2),
        post(3, text="два", entities=(Entity(B, 0, 3),)),
    ]
    assert merge(posts) == ("один\nдва", (Entity(B, 0, 4), Entity(B, 5, 3)))


def test_truncate_cuts_at_a_space_and_clips_entities() -> None:
    text = "слово " * 10
    cut, entities = truncate(text, (Entity(B, 0, 60), Entity(B, 40, 5)), 20)
    assert cut == "слово слово слово…"
    assert utf16_len(cut) <= 20
    assert entities == (Entity(B, 0, 17),)


def test_truncate_counts_utf16() -> None:
    # "😂" takes two UTF-16 code units
    cut, entities = truncate("😂 жирный курсив", (Entity(B, 3, 6), Entity(EntityKind.ITALIC, 10, 6)), 12)
    assert (cut, entities) == ("😂 жирный…", (Entity(B, 3, 6),))


def test_truncate_cuts_a_long_word_when_there_is_no_space_nearby() -> None:
    cut, _ = truncate("коротко " + "о" * 100, (), 50)
    assert cut == "коротко " + "о" * 41 + "…"


def test_truncate_does_not_split_surrogate_pairs() -> None:
    cut, _ = truncate("a" + "😂" * 10, (), 6)
    assert cut == "a😂😂…"
    assert utf16_len(cut) == 6


def test_truncate_keeps_short_text() -> None:
    assert truncate("коротко", (Entity(B, 0, 3),), 20) == ("коротко", (Entity(B, 0, 3),))


def test_caption_without_text_is_the_link_only() -> None:
    assert build_caption(group(post(1)), "pupaslupas", TZ) == Caption(FOOTER, (link(0),))


@pytest.mark.parametrize("text", ["#shrek #mashup", "#мем, #юмор.", "  "])
def test_caption_of_only_hashtags_is_dropped(text: str) -> None:
    assert build_caption(group(post(1, text=text)), "pupaslupas", TZ) == Caption(FOOTER, (link(0),))


@pytest.mark.parametrize(
    "text", ["Skyrim #gaming", "#мем 😂", "Современные проблемы требуют современных решений #tech"]
)
def test_caption_with_other_text_is_kept_as_is(text: str) -> None:
    caption = build_caption(group(post(1, text=text)), "pupaslupas", TZ)
    assert caption == Caption(f"{text}\n\n{FOOTER}", (link(utf16_len(text) + 2),))


def test_caption_keeps_album_text_and_formatting_without_parsing_markdown() -> None:
    text = "#мем Очень **смешно**"
    album = group(post(1, grouped_id=9), post(2, grouped_id=9, text=text, entities=(Entity(B, 13, 6),)))
    caption = build_caption(album, "pupaslupas", TZ)
    assert caption.text == f"{text}\n\n{FOOTER}"
    assert caption.entities == (Entity(B, 13, 6), link(23))


def test_caption_is_cut_to_the_limit() -> None:
    caption = build_caption(group(post(1, text="а" * 2000)), "pupaslupas", TZ)
    assert utf16_len(caption.text) == CAPTION_LIMIT
    assert caption.text.endswith(f"а…\n\n{FOOTER}")
    assert caption.entities == (link(CAPTION_LIMIT - len(FOOTER)),)


def test_caption_year_is_in_the_channel_timezone() -> None:
    # 20:00 UTC on Dec 31 is already Jan 1 in Yekaterinburg
    new_year = group(post(7, date=datetime(2019, 12, 31, 20, tzinfo=UTC)))
    assert build_caption(new_year, "pupaslupas", TZ) == Caption("2020 #MemeThrowback", (link(0, 7, "2020"),))
