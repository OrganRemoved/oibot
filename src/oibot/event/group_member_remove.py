from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.api.send_message import Message, SendMessageResponse
from oibot.event import Event


class GroupMemberRemoveEvent(Event):
    event_type: ClassVar[Literal["GROUP_MEMBER_REMOVE"]] = "GROUP_MEMBER_REMOVE"

    timestamp: datetime
    group_openid: str
    member_openid: str

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: str | Message, **kwargs) -> SendMessageResponse:
        if isinstance(message, str):
            message = Message.content(content=message)

        return await self.bot.send_message(
            message=message, group_openid=self.group_openid, **kwargs
        )
