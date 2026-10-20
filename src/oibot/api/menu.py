from datetime import timedelta
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from oibot.api import CompactDict, sliding_window_rate_limit

if TYPE_CHECKING:
    from oibot.bot import OiBot


class MenuSwitch(TypedDict):
    switch_id: str
    default: bool


class SubMenuItem(TypedDict):
    name: str
    type: Literal["send_message", "link"]
    send_message: NotRequired[str]
    link: NotRequired[str]


class MenuItem(TypedDict):
    name: str
    type: Literal["switch", "send_message", "link", "menu"]
    sub_menu_items: NotRequired[list[SubMenuItem]]
    send_message: NotRequired[str]
    link: NotRequired[str]
    switch: NotRequired[MenuSwitch]
    align: NotRequired[Literal["left", "right"]]


class Menu(TypedDict):
    items: list[MenuItem]


class GetGlobalMenuResponse(TypedDict):
    version: int
    menu: NotRequired[Menu]


class UpdateGlobalMenuResponse(TypedDict):
    version: int


class MenuMixin:
    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_global_menu(self: OiBot) -> GetGlobalMenuResponse:
        return await self(HTTPMethod.GET, "/v2/menu")

    @sliding_window_rate_limit(limit=5, window=timedelta(minutes=1))
    async def update_global_menu(
        self: OiBot, *, menu: Menu | None = None
    ) -> UpdateGlobalMenuResponse:
        return await self(HTTPMethod.PUT, "/v2/menu", json=CompactDict(menu=menu))
