from oibot.mixin import MixinProtocol


class RecallMessageMixin:
    async def recall_private_message(
        self: MixinProtocol, *, openid: str, message_id: str
    ) -> None:
        return await self(
            "DELETE",
            f"/v2/users/{openid}/messages/{message_id}",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
        )

    async def recall_group_message(
        self: MixinProtocol, *, group_openid: str, message_id: str
    ) -> None:
        return await self(
            "DELETE",
            f"/v2/groups/{group_openid}/messages/{message_id}",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
        )

    async def recall_channel_message(
        self: MixinProtocol, *, channel_id: str, message_id: str, hide_tip: bool = False
    ) -> None:
        return await self(
            "DELETE",
            f"/channels/{channel_id}/messages/{message_id}",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            params={"htdetip": hide_tip},
        )

    async def recall_guild_message(
        self: MixinProtocol, *, guild_id: str, message_id, hide_tip: bool = False
    ) -> None:
        return await self(
            "DELETE",
            f"/dms/{guild_id}/messages/{message_id}",
            headers={"Authorization": f"QQBot {await self.get_app_access_token()}"},
            params={"htdetip": hide_tip},
        )
