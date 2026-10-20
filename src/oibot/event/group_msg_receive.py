from datetime import datetime
from functools import cached_property
from typing import ClassVar

from oibot.api.message import Keyboard, Message, MessageResponse
from oibot.event import Event, EventType


class GroupMsgReceiveEvent(Event):
    event_type: ClassVar[EventType] = EventType.GROUP_MSG_RECEIVE

    group_openid: str
    op_member_openid: str
    timestamp: datetime

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: Message | Message[Keyboard]) -> MessageResponse:
        return await self.bot.send_group_message(
            group_openid=self.group_openid, message=message
        )
