from datetime import datetime
from typing import ClassVar, Literal

from oibot.api.send_message import (
    Ark,
    Keyboard,
    Markdown,
    SendMessageResponse,
    send_message,
)
from oibot.event import Context, Event


class GroupAddRobotEvent(Event):
    __slots__ = ("__weakref__", "timestamp", "group_openid", "op_member_openid")

    event_type: ClassVar[Literal["GROUP_ADD_ROBOT"]] = "GROUP_ADD_ROBOT"

    timestamp: datetime
    group_openid: str
    op_member_openid: str

    def __init__(self, *, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.group_openid = d["group_openid"]
        self.op_member_openid = d["op_member_openid"]

        super().__init__(ctx=ctx)

    async def reply(
        self,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        ark: Ark | None = None,
        image: bytes | str | None = None,
        video: bytes | str | None = None,
        voice: bytes | str | None = None,
    ) -> SendMessageResponse:
        return await send_message(
            group_openid=self.group_openid,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            ark=ark,
            image=image,
            video=video,
            voice=voice,
            event_id=self._id,
        )
