from datetime import datetime
from functools import cached_property
from typing import ClassVar

from oibot.event import Event, EventType


class GroupDelRobotEvent(Event):
    event_type: ClassVar[EventType] = EventType.GROUP_DEL_ROBOT

    timestamp: datetime
    group_openid: str
    op_member_openid: str

    @cached_property
    def openid(self) -> str:
        return self.op_member_openid

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])
