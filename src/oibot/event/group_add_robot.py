from datetime import datetime
from typing import ClassVar, Literal

from oibot.bot import OiBot
from oibot.event import Context, Event
from oibot.mixin.send_message import (
    Ark,
    Embed,
    Keyboard,
    Markdown,
    Media,
    MessageReference,
    SendMessageResponse,
)


class GroupAddRobotEvent(Event):
    __slots__ = ("timestamp", "group_openid", "op_member_openid")

    event_type: ClassVar[Literal["GROUP_ADD_ROBOT"]] = "GROUP_ADD_ROBOT"

    timestamp: datetime
    group_openid: str
    op_member_openid: str

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.group_openid = d["group_openid"]
        self.op_member_openid = d["op_member_openid"]

        super().__init__(bot, ctx)

    async def reply(
        self,
        content: str | None = None,
        markdown: Markdown | None = None,
        keyboard: Keyboard | None = None,
        embed: Embed | None = None,
        ark: Ark | None = None,
        media: Media | None = None,
        message_reference: MessageReference | None = None,
        event_id: str | None = None,
        msg_id: str | None = None,
        msg_seq: int = 0,
    ) -> SendMessageResponse:
        return await self.bot.send_group_message(
            group_openid=self.group_openid,
            content=content,
            markdown=markdown,
            keyboard=keyboard,
            embed=embed,
            ark=ark,
            media=media,
            message_reference=message_reference,
            event_id=event_id,
            msg_id=msg_id,
            msg_seq=msg_seq,
        )
