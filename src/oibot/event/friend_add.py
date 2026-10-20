from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import ClassVar

from oibot.api.message import Keyboard, Message, MessageResponse
from oibot.event import Event, EventType


class FriendAddEvent(Event):
    @dataclass(frozen=True, slots=True)
    class Author:
        union_openid: str

    event_type: ClassVar[EventType] = EventType.FRIEND_ADD

    timestamp: datetime
    openid: str
    scene: int
    scene_param: str
    author: Author

    @cached_property
    def author(self) -> Author:
        return self.Author(union_openid=self.ctx["d"]["author"]["union_openid"])

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])

    async def reply(self, message: Message | Message[Keyboard]) -> MessageResponse:
        return await self.bot.send_user_message(openid=self.openid, message=message)
