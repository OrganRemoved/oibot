from oibot.bot import OiBot


async def recall_private_message(*, openid: str, message_id: str) -> None:
    return await OiBot.request(
        method="DELETE", url=f"/v2/users/{openid}/messages/{message_id}"
    )


async def recall_group_message(*, group_openid: str, message_id: str) -> None:
    return await OiBot.request(
        method="DELETE", url=f"/v2/groups/{group_openid}/messages/{message_id}"
    )


async def recall_channel_message(
    *, channel_id: str, message_id: str, hide_tip: bool = False
) -> None:
    return await OiBot.request(
        method="DELETE",
        url=f"/channels/{channel_id}/messages/{message_id}",
        params={"htdetip": hide_tip},
    )


async def recall_guild_message(
    *, guild_id: str, message_id, hide_tip: bool = False
) -> None:
    return await OiBot.request(
        method="DELETE",
        url=f"/dms/{guild_id}/messages/{message_id}",
        params={"htdetip": hide_tip},
    )
