from datetime import datetime
from typing import ClassVar, Literal

from oibot.api.send_message import (
    Ark,
    Embed,
    Keyboard,
    Markdown,
    Media,
    MessageReference,
    SendMessageResponse,
)
from oibot.event import Event


class GroupAddRobotEvent(Event):
    event_type: ClassVar[Literal["GROUP_ADD_ROBOT"]] = "GROUP_ADD_ROBOT"

    timestamp: datetime
    group_openid: str
    op_member_openid: str

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
