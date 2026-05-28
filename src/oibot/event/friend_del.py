from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal, NamedTuple

from oibot.event import Event


class FriendDelEvent(Event):
    class Author(NamedTuple):
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_DEL"]] = "FRIEND_DEL"

    timestamp: datetime
    openid: str
    author: Author

    @cached_property
    def author(self) -> Author:
        author = self.ctx["d"]["author"]

        return self.Author(union_openid=author["union_openid"])
