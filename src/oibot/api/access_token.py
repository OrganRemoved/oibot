import asyncio
from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from oibot.bot import OiBot


class AccessToken(TypedDict):
    access_token: str
    expires_in: str


class AccessTokenMixin:
    async def get_app_access_token(
        self: OiBot, app_id: str, app_secret: str
    ) -> AccessToken:
        async with self.client_session.post(
            "/app/getAppAccessToken", json={"appId": app_id, "clientSecret": app_secret}
        ) as response:
            return await response.json()

    async def get_access_token(self: OiBot, app_id: str, app_secret: str) -> str:
        if future := self.app.get(key := (app_id, app_secret)):
            return await asyncio.shield(future)

        loop = asyncio.get_running_loop()

        self.app[key] = future = loop.create_future()

        try:
            result = await self.get_app_access_token(app_id, app_secret)

            future.set_result(access_token := result["access_token"])

            loop.call_later(
                int(result["expires_in"]) - 60,
                lambda: self.app.get(key) is future and self.app.pop(key),
            )

            return access_token

        except asyncio.CancelledError:
            future.cancel()

        except BaseException as e:
            future.set_exception(e)

        if self.app.get(key) is future:
            self.app.pop(key)

        return await future
