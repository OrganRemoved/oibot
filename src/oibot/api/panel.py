from datetime import timedelta
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from oibot.api import CompactDict, sliding_window_rate_limit

if TYPE_CHECKING:
    from oibot.bot import OiBot


class PanelItem(TypedDict):
    name: str
    type: Literal["command", "link"]
    desc: NotRequired[str]
    only_admin: NotRequired[bool]
    link: NotRequired[str]


class Panel(TypedDict):
    items: list[PanelItem]
    remark: NotRequired[str]
    version: NotRequired[int]


class PanelRecord(TypedDict):
    panel_id: str
    scope: Literal["c2c", "group", "channel", "dm"]
    target_type: Literal["all", "specific"]
    panel: Panel
    created_at: str
    updated_at: str
    version: int


class PanelDetail(PanelRecord):
    user_openids: NotRequired[list[str]]
    group_openids: NotRequired[list[str]]


class PanelListResponse(TypedDict):
    records: list[PanelRecord]
    next_cursor: str
    is_end: bool


class CreatePanelResponse(TypedDict):
    panel_id: str


class UpdatePanelResponse(TypedDict):
    version: int


class PanelMixin:
    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_panels(
        self: OiBot,
        *,
        scope: Literal["c2c", "group", "channel", "dm"],
        cursor: str | None = None,
        limit: int | None = None,
    ) -> PanelListResponse:
        return await self(
            HTTPMethod.GET,
            "/v2/panels",
            params=CompactDict(scope=scope, cursor=cursor, limit=limit),
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(minutes=1))
    async def create_panel(
        self: OiBot,
        *,
        scope: Literal["c2c", "group", "channel", "dm"],
        panel: Panel,
        target_type: Literal["all", "specific"] | None = None,
        user_openids: list[str] | None = None,
        group_openids: list[str] | None = None,
    ) -> CreatePanelResponse:
        return await self(
            HTTPMethod.POST,
            "/v2/panels",
            json=CompactDict(
                scope=scope,
                target_type=target_type,
                user_openids=user_openids,
                group_openids=group_openids,
                panel=panel,
            ),
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_panel(self: OiBot, *, panel_id: str) -> PanelDetail:
        return await self(HTTPMethod.GET, f"/v2/panels/{panel_id}")

    @sliding_window_rate_limit(limit=10, window=timedelta(minutes=1))
    async def update_panel(
        self: OiBot, *, panel_id: str, panel: Panel
    ) -> UpdatePanelResponse:
        return await self(
            HTTPMethod.PUT, f"/v2/panels/{panel_id}", json={"panel": panel}
        )

    @sliding_window_rate_limit(limit=10, window=timedelta(minutes=1))
    async def delete_panel(self: OiBot, *, panel_id: str) -> None:
        return await self(HTTPMethod.DELETE, f"/v2/panels/{panel_id}")

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def update_panel_target(
        self: OiBot,
        *,
        panel_id: str,
        op: Literal["add", "del"],
        user_openids: list[str] | None = None,
        group_openids: list[str] | None = None,
    ) -> None:
        return await self(
            HTTPMethod.PUT,
            f"/v2/panels/{panel_id}/target",
            json=CompactDict(
                op=op, user_openids=user_openids, group_openids=group_openids
            ),
        )
