from telethon import types as tg
from random import random

from message import GroupedMessages

__evaluated_entry = tuple[GroupedMessages, float]

negative_emoticons = ('👎', '💩', '🥱', '🤔')

def sort_by_best(messages: list[GroupedMessages]) -> list[GroupedMessages] | None:
    assert len(messages) > 0
    evaluatable = False
    evaluated: list[__evaluated_entry] = list()
    for group in messages:
        score: float = __score_group(group)
        if score != 0:
            evaluatable = True
        if score < 0:
            # skip bad posts
            continue
        score += random() / 2. # randomize messages inside their tier
        evaluated.append((group, score))
    if not evaluatable:
        # all scores are 0, nothing to sort by
        return None
    evaluated = sorted(evaluated, key=(lambda e: e[1]), reverse=True)
    return list(map((lambda e: e[0]), evaluated))

def __score_group(group: GroupedMessages) -> int:
    post = group.first()
    if post.reactions == None:
        return 0
    score = 0
    for reaction in post.reactions.results:
        score += __emoji_score(reaction)
    return score

def __emoji_score(r: tg.ReactionCount) -> int:
    if not isinstance(r.reaction, tg.ReactionEmoji):
        return 0
    emoticon = r.reaction.emoticon
    if emoticon in negative_emoticons:
        score = -1
    else:
        score = 1
    return score * r.count
