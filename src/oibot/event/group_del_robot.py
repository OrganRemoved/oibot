from datetime import datetime
from typing import ClassVar, Literal

from oibot.bot import OiBot
from oibot.event import Context, Event


class GroupDelRobotEvent(Event):
    __slots__ = ("timestamp", "group_openid", "op_member_openid")

    event_type: ClassVar[Literal["GROUP_DEl_ROBOT"]] = "GROUP_DEl_ROBOT"

    timestamp: datetime
    group_openid: str
    op_member_openid: str

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.group_openid = d["group_openid"]
        self.op_member_openid = d["op_member_openid"]

        super().__init__(bot, ctx)
