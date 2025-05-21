import logging
from typing import ClassVar, TypedDict


class Context(TypedDict):
    d: dict
    id: str
    op: int
    s: int
    t: str


class Event:
    __slots__ = ("_d", "_id", "_op", "_s", "_t")

    _d: dict
    _id: str
    _op: int
    _s: int
    _t: str

    event_type: ClassVar[str]

    event: ClassVar[dict[str, type["Event"]]] = {}

    def __init__(self, *, ctx: Context) -> None:
        self._d = ctx["d"]
        self._id = ctx["id"]
        self._op = ctx["op"]
        # self._s = ctx["s"]
        self._t = ctx["t"]

        logging.info(self.__repr__())

    def __init_subclass__(cls, *args, **kwargs) -> None:
        logging.debug(f"registered {cls} as type {cls._t}")

        Event.event[cls.event_type] = cls

    def __repr__(self) -> str:
        return f"""{self.__class__.__name__}({
            ", ".join(
                f"{item}={value}"
                for item in self.__slots__
                if (not item.startswith("__")) and (value := getattr(self, item, None))
            )
        })"""

    @classmethod
    def dispatch(cls, *, ctx: Context) -> "Event":
        return event(ctx=ctx) if (event := cls.event.get(ctx["t"])) else cls(ctx=ctx)
