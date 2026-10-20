import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from http import HTTPMethod
from inspect import isasyncgenfunction, isgeneratorfunction
from types import TracebackType
from typing import Any, Self

from aiohttp import ClientHandlerType, ClientRequest, ClientResponse, ClientSession, web

from oibot.api.access_token import AccessTokenMixin
from oibot.api.group_management import (
    GroupJoinApprovalStrategyMixin,
    GroupManagementMixin,
)
from oibot.api.interaction import InteractionMixin
from oibot.api.menu import MenuMixin
from oibot.api.message import SendMessageMixin
from oibot.api.panel import PanelMixin
from oibot.api.profile import ProfileMixin
from oibot.api.recall import DeleteMessageMixin
from oibot.api.rich_media import RichMediaMixin
from oibot.matcher import ensure_async
from oibot.plugin import PluginManager, QuotaPool, SessionManager
from oibot.transport.webhook import WebhookMixin
from oibot.transport.websocket import Intents, WebSocketMixin


class OiBot(
    AccessTokenMixin,
    DeleteMessageMixin,
    GroupJoinApprovalStrategyMixin,
    GroupManagementMixin,
    InteractionMixin,
    MenuMixin,
    PanelMixin,
    ProfileMixin,
    RichMediaMixin,
    SendMessageMixin,
    WebhookMixin,
    WebSocketMixin,
):
    __slots__ = (
        "app",
        "client_session",
        "plugin_manager",
        "quota_pool",
        "session_manager",
    )

    def __init__(
        self,
        plugins: str | Iterable[str] | None = None,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        **kwargs: Any,
    ) -> None:
        self.plugin_manager = plugin_manager = PluginManager()
        self.quota_pool = QuotaPool()
        self.session_manager = SessionManager()

        if isinstance(plugins, str):
            plugin_manager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                plugin_manager.import_from(plugin)

        self.app = app = web.Application(**kwargs)

        app.update(
            bot=self,
            app_id=ContextVar("app_id", default=app_id),
            app_secret=ContextVar("app_secret", default=app_secret),
        )

        async def init(app: web.Application) -> AsyncIterator[None]:
            async with AsyncExitStack() as stack:
                for plugin in self.plugin_manager.plugins.values():
                    if init := plugin.init:
                        if isasyncgenfunction(init):
                            await stack.enter_async_context(
                                asynccontextmanager(init)(app)
                            )

                        elif isgeneratorfunction(init):
                            stack.enter_context(contextmanager(init)(app))

                        else:
                            stack.callback(
                                asyncio.create_task(
                                    ensure_async(init, to_thread=True)(app)
                                ).cancel
                            )

                yield

        app.cleanup_ctx.append(init)

    async def __aenter__(self) -> Self:
        self.client_session = ClientSession(
            base_url="https://api.bot.qq.com",
            raise_for_status=True,
            middlewares=(self.middleware,),
        )

        await self.client_session.__aenter__()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self.client_session.__aexit__(exc_type, exc_value, traceback)

    async def __call__(self, method: HTTPMethod, url: str, **kwargs: Any) -> Any:
        logging.debug(f"{method=} {url=} {kwargs=}")

        async with self.client_session.request(method, url, **kwargs) as response:
            if data := await response.read():
                return json.loads(data)

    @property
    def app_id(self) -> str:
        return self.app["app_id"].get()

    @property
    def app_secret(self) -> str:
        return self.app["app_secret"].get()

    async def middleware(
        self, request: ClientRequest, handler: ClientHandlerType
    ) -> ClientResponse:
        if request.url.path != "/app/getAppAccessToken":
            request.headers["Authorization"] = (
                f"QQBot {await self.get_access_token(self.app_id, self.app_secret)}"
            )

        return await handler(request)

    def webhook(
        self, *, path: str = "/", host: str = "0.0.0.0", port: int = 8080, **kwargs: Any
    ) -> None:
        WebhookMixin.__init__(self, path=path, **kwargs)

        self.webhook_run(host=host, port=port)

    def websocket(
        self,
        *,
        intents: Intents = Intents.GROUP_AND_C2C_EVENT,
        shard: tuple[int, int] = (0, 1),
        properties: dict[str, str] = {},
        host: str = "0.0.0.0",
        port: int = 8080,
        **kwargs: Any,
    ) -> None:
        WebSocketMixin.__init__(self)

        self.websocket_run(
            intents=intents,
            shard=shard,
            properties=properties,
            host=host,
            port=port,
            **kwargs,
        )
