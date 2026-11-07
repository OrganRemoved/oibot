from datetime import timedelta
from enum import IntEnum
from http import HTTPMethod
from typing import TYPE_CHECKING

from oibot.api import sliding_window_rate_limit

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
    @sliding_window_rate_limit(limit=50, window=timedelta(seconds=1))
    async def acknowledge_interaction(
        self: OiBot, *, interaction_id: str, code: Code
    ) -> None:
        return await self(
            HTTPMethod.PUT, f"/interactions/{interaction_id}", json={"code": code}
        )
