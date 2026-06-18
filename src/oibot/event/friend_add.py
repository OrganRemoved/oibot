from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.api.send_message import Message, SendMessageResponse
from oibot.event import Event


class FriendAddEvent(Event):
    @dataclass(frozen=True, slots=True)
    class Author:
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_ADD"]] = "FRIEND_ADD"

    timestamp: datetime
    openid: str
    author: Author

    @cached_property
    def author(self) -> Author:
        return self.Author(union_openid=self.ctx["d"]["author"]["union_openid"])

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: str | Message, **kwargs) -> SendMessageResponse:
        if isinstance(message, str):
            message = Message.content(content=message)

        return await self.bot.send_message(
            message=message, openid=self.author.union_openid, **kwargs
        )
