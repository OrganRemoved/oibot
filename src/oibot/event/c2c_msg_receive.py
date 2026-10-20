from datetime import datetime
from functools import cached_property
from typing import ClassVar

from oibot.api.message import Keyboard, Message, MessageResponse
from oibot.event import Event, EventType


class C2CMsgReceiveEvent(Event):
    event_type: ClassVar[EventType] = EventType.C2C_MSG_RECEIVE

    openid: str
    timestamp: datetime

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: Message | Message[Keyboard]) -> MessageResponse:
        return await self.bot.send_user_message(openid=self.openid, message=message)
