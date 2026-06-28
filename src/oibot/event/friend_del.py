from dataclasses import dataclass
from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.event import Event


class FriendDelEvent(Event):
    @dataclass(frozen=True, slots=True)
    class Author:
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_DEL"]] = "FRIEND_DEL"

    timestamp: datetime
    openid: str
    author: Author

    @cached_property
    def author(self) -> Author:
        return self.Author(union_openid=self.ctx["d"]["author"]["union_openid"])

    @cached_property
    def timestamp(self) -> datetime:
        return datetime.fromtimestamp(self.ctx["d"]["timestamp"])
