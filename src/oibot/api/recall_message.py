from http import HTTPMethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oibot.bot import OiBot


class DeleteMessageMixin:
    async def delete_user_message(
        self: "OiBot", *, openid: str, message_id: str
    ) -> None:
        return await self(
            HTTPMethod.DELETE,
            f"/v2/users/{openid}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
        )

    async def delete_group_message(
        self: "OiBot", *, group_openid: str, message_id: str
    ) -> None:
        return await self(
            HTTPMethod.DELETE,
            f"/v2/groups/{group_openid}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
        )

    async def delete_channel_message(
        self: "OiBot",
        *,
        channel_id: str,
        message_id: str,
        hide_tip: bool = False,
    ) -> None:
        return await self(
            HTTPMethod.DELETE,
            f"/channels/{channel_id}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            params={"hide_tip": hide_tip},
        )

    async def delete_guild_message(
        self: "OiBot", *, guild_id: str, message_id, hide_tip: bool = False
    ) -> None:
        return await self(
            HTTPMethod.DELETE,
            f"/dms/{guild_id}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            params={"hide_tip": hide_tip},
        )
