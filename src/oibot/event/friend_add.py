from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal, NamedTuple

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


class FriendAddEvent(Event):
    class Author(NamedTuple):
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_ADD"]] = "FRIEND_ADD"

    timestamp: datetime
    openid: str
    author: Author

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(union_openid=author["union_openid"])

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
        return await self.bot.send_private_message(
            openid=self.author.union_openid,
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
