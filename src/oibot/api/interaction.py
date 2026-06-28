from enum import IntEnum
from http import HTTPMethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from oibot.bot import OiBot


class Code(IntEnum):
    SUCCESS = 0
    FAILURE = 1
    RATE_LIMIT_EXCEEDED = 2
    DUPLICATE_OPERATION = 3
    PERMISSION_DENIED = 4
    REQUIRES_ADMIN_PRIVILEGES = 5


class InteractionMixin:
    async def interaction(self: "OiBot", *, interaction_id: str, code: Code) -> Any:
        return await self(
            HTTPMethod.PUT,
            f"/interactions/{interaction_id}",
            headers={
                "Authorization": f"QQBot {await self.get_access_token(app_id=self.app_id, app_secret=self.app_secret)}"
            },
            json={"code": code},
        )
