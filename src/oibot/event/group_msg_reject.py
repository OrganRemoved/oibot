from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.event import Event


class GroupMsgReject(Event):
    event_type: ClassVar[Literal["GROUP_MSG_REJECT"]] = "GROUP_MSG_REJECT"

    group_openid: str
    op_member_openid: str
    timestamp: datetime

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])
