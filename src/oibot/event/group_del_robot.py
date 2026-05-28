from datetime import datetime
from typing import ClassVar, Literal

from oibot.event import Event


class GroupDelRobotEvent(Event):
    event_type: ClassVar[Literal["GROUP_DEL_ROBOT"]] = "GROUP_DEL_ROBOT"

    timestamp: datetime
    group_openid: str
    op_member_openid: str
