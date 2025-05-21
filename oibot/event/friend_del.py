from datetime import datetime
from typing import ClassVar, Literal

from oibot.event import Context, Event


class FriendDel(Event):
    __slots__ = ("__weakref__", "timestamp", "openid", "author")

    class Author:
        __slots__ = ("union_openid",)

        def __init__(self, *, union_openid: str) -> None:
            self.union_openid = union_openid

    event_type: ClassVar[Literal["FRIEND_DEL"]] = "FRIEND_DEL"

    timestamp: datetime
    openid: str
    author: Author

    def __init__(self, *, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.openid = d["openid"]
        self.author = self.Author(union_openid=d["author"]["union_openid"])

        super().__init__(ctx=ctx)
