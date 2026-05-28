from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from oibot.bot import OiBot


class RecallMessageMixin:
    async def recall_private_message(
        self: "OiBot", *, openid: str, message_id: str
    ) -> None:
        return await self(
            "DELETE",
            f"/v2/users/{openid}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
        )

    async def recall_group_message(
        self: "OiBot", *, group_openid: str, message_id: str
    ) -> None:
        return await self(
            "DELETE",
            f"/v2/groups/{group_openid}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
        )

    async def recall_channel_message(
        self: "OiBot",
        *,
        channel_id: str,
        message_id: str,
        hide_tip: bool = False,
    ) -> None:
        return await self(
            "DELETE",
            f"/channels/{channel_id}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            params={"htdetip": hide_tip},
        )

    async def recall_guild_message(
        self: "OiBot", *, guild_id: str, message_id, hide_tip: bool = False
    ) -> None:
        return await self(
            "DELETE",
            f"/dms/{guild_id}/messages/{message_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            params={"htdetip": hide_tip},
        )
