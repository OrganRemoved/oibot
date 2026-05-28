import asyncio
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from oibot.bot import OiBot


class AccessToken(TypedDict):
    access_token: str
    expires_in: str


class AccessTokenMixin:
    futures: dict[tuple[str, str], asyncio.Future[str]] = {}

    async def get_app_access_token(
        self: "OiBot", app_id: str, app_secret: str
    ) -> AccessToken:
        return await self(
            "POST",
            "https://bots.qq.com/app/getAppAccessToken",
            json={"appId": app_id, "clientSecret": app_secret},
        )

    async def get_access_token(self: "OiBot", app_id: str, app_secret: str) -> str:
        if future := self.futures.get(key := (app_id, app_secret)):
            return await future

        loop = asyncio.get_running_loop()

        self.futures[key] = future = loop.create_future()

        try:
            result = await self.get_app_access_token(app_id, app_secret)

            future.set_result(access_token := result["access_token"])

            loop.call_later(
                int(result["expires_in"]) - 60, lambda: self.futures.pop(key, None)
            )

            return access_token

        except BaseException as e:
            self.futures.pop(key, None)

            future.set_exception(e)

            raise
