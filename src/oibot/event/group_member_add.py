from datetime import datetime
from functools import cached_property
from typing import ClassVar

from oibot.api.message import Keyboard, Message, MessageResponse
from oibot.event import Event, EventType


class GroupMemberAddEvent(Event):
    event_type: ClassVar[EventType] = EventType.GROUP_MEMBER_ADD

    timestamp: datetime
    group_openid: str
    member_openid: str

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: Message | Message[Keyboard]) -> MessageResponse:
        return await self.bot.send_group_message(
            group_openid=self.group_openid, message=message
        )
