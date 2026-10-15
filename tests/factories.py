from datetime import UTC, datetime

from throwback.model import Group, MediaKind, Post

DATE = datetime(2019, 10, 15, 12, tzinfo=UTC)


def post(
    id: int,
    media: MediaKind = MediaKind.PHOTO,
    text: str = "",
    grouped_id: int | None = None,
    author: str | None = None,
    reply_to: int | None = None,
    reactions: dict[str, int] | None = None,
    date: datetime = DATE,
) -> Post:
    return Post(
        id=id,
        date=date,
        media=media,
        text=text,
        grouped_id=grouped_id,
        author=author,
        reply_to=reply_to,
        reactions=reactions or {},
    )


def group(*posts: Post) -> Group:
    return Group(tuple(posts))
