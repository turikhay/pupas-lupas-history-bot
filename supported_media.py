from typing import TypeGuard
from telethon import types as tg

SupportedMediaType = tg.MessageMediaPhoto | tg.MessageMediaDocument

def is_supported_media(e) -> TypeGuard[SupportedMediaType]:
    return isinstance(e, tg.MessageMediaPhoto) or isinstance(e, tg.MessageMediaDocument)

