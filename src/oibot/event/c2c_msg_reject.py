from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.event import Event


class C2CMsgRejectEvent(Event):
    event_type: ClassVar[Literal["C2C_MSG_REJECT"]] = "C2C_MSG_REJECT"

    openid: str
    timestamp: datetime

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])
