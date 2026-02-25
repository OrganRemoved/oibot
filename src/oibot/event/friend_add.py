from datetime import datetime
from typing import ClassVar, Literal, NamedTuple

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


class FriendAddEvent(Event):
    __slots__ = ("timestamp", "openid", "author")

    class Author(NamedTuple):
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_ADD"]] = "FRIEND_ADD"

    timestamp: datetime
    openid: str
    author: Author

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.openid = d["openid"]
        self.author = self.Author(union_openid=d["author"]["union_openid"])

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
