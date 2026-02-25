from datetime import datetime
from typing import ClassVar, Literal, NamedTuple

from oibot.bot import OiBot
from oibot.event import Context, Event


class FriendDelEvent(Event):
    __slots__ = ("timestamp", "openid", "author")

    class Author(NamedTuple):
        union_openid: str

    event_type: ClassVar[Literal["FRIEND_DEL"]] = "FRIEND_DEL"

    timestamp: datetime
    openid: str
    author: Author

    def __init__(self, bot: OiBot, ctx: Context) -> None:
        d = ctx["d"]

        self.timestamp = d["timestamp"]
        self.openid = d["openid"]
        self.author = self.Author(union_openid=d["author"]["union_openid"])

        super().__init__(bot, ctx)
