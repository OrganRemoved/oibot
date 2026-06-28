from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.event import Event


class GroupMsgReceiveEvent(Event):
    event_type: ClassVar[Literal["GROUP_MSG_RECEIVE"]] = "GROUP_MSG_RECEIVE"

    group_openid: str
    op_member_openid: str
    timestamp: datetime

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])
