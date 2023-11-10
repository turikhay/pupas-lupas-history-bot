from datetime import datetime
from telethon import types as tg

class GroupedMessages():
    def __init__(self, id: int, msg_id: int, date: datetime) -> None:
        self.id = id
        self.msg_id = id
        self.date = date
        self.messages: list[tg.Message] = list()

    def first(self):
        assert len(self.messages) > 0
        return self.messages[0]

    def __str__(self) -> str:
        return "GroupedMessages{id=%d,msg_id=%d,date=%s,messages_count=%d}" % (self.id, self.msg_id, self.date, len(self.messages))
