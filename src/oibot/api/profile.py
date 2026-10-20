from datetime import timedelta
from http import HTTPMethod
from typing import TYPE_CHECKING, NotRequired, TypedDict

from oibot.api import CompactDict, sliding_window_rate_limit

if TYPE_CHECKING:
    from oibot.bot import OiBot


class BotInformation(TypedDict):
    id: str
    username: str
    avatar: str
    bot: bool
    union_openid: NotRequired[str]
    union_user_account: NotRequired[str]
    share_url: NotRequired[str]
    welcome_msg: NotRequired[str]


class GuildInformation(TypedDict):
    id: str
    name: str
    icon: str
    owner_id: str
    owner: bool
    joined_at: str
    member_count: int
    max_members: int
    description: str


class URLLinkData(TypedDict):
    url: str


class URLLinkResponse(TypedDict):
    data: URLLinkData


class ProfileMixin:
    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def generate_url_link(
        self: OiBot, *, callback_data: str | None = None
    ) -> URLLinkResponse:
        return await self(
            HTTPMethod.POST,
            "/v2/generate_url_link",
            json=CompactDict(callback_data=callback_data),
        )

    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def get_bot_guilds(
        self: OiBot,
        *,
        before: str | None = None,
        after: str | None = None,
        limit: int | None = None,
    ) -> list[GuildInformation]:
        return await self(
            HTTPMethod.GET,
            "/users/@me/guilds",
            params=CompactDict(before=before, after=after, limit=limit),
        )

    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def get_bot_information(self: OiBot) -> BotInformation:
        return await self(HTTPMethod.GET, "/users/@me")
