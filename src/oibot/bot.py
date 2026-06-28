import asyncio
import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from http import HTTPMethod, HTTPStatus
from inspect import isasyncgenfunction, isgeneratorfunction
from types import TracebackType
from typing import Any, AsyncIterator, Iterable, Self

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.api.access_token import AccessTokenMixin
from oibot.api.interaction import InteractionMixin
from oibot.api.recall_message import DeleteMessageMixin
from oibot.api.send_message import SendMessageMixin
from oibot.api.upload_file import UploadFileMixin
from oibot.event import OP, Event
from oibot.matcher import ensure_async, fire_and_forget
from oibot.plugin import PluginManager, SessionManager


class OiBot(
    AccessTokenMixin,
    InteractionMixin,
    DeleteMessageMixin,
    SendMessageMixin,
    UploadFileMixin,
):
    __slots__ = ("app", "plugin_manager", "session_manager", "session")

    def __init__(
        self,
        plugins: str | Iterable[str] | None = None,
        *,
        app_id: str | None = None,
        app_secret: str | None = None,
        **kwargs,
    ) -> None:

        self.plugin_manager = plugin_manager = PluginManager()
        self.session_manager = SessionManager()

        if isinstance(plugins, str):
            plugin_manager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                plugin_manager.import_from(plugin)

        self.app = app = web.Application(**kwargs)

        app.router.add_post(path="/", handler=self.handler)

        app["bot"] = self

        app["app_id"] = ContextVar("app_id", default=app_id)
        app["app_secret"] = ContextVar("app_secret", default=app_secret)

        async def init_ctx(app: web.Application) -> AsyncIterator[None]:
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
                                fire_and_forget(
                                    ensure_async(init, to_thread=True)(app)
                                ).cancel
                            )

                yield

        app.cleanup_ctx.append(init_ctx)

    async def __aenter__(self) -> Self:
        self.session = ClientSession(
            base_url="https://api.sgroup.qq.com", raise_for_status=True
        )

        await self.session.__aenter__()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None = None,
        exc_value: BaseException | None = None,
        traceback: TracebackType | None = None,
    ) -> None:
        await self.session.__aexit__(exc_type, exc_value, traceback)

    async def __call__(self, method: HTTPMethod, url: str, **kwargs) -> Any:
        logging.debug(f"{method=} {url=} {kwargs=}")

        async with self.session.request(method, url, **kwargs) as resp:
            if data := await resp.read():
                return json.loads(data)

    @property
    def app_id(self) -> str:
        return self.app["app_id"].get()

    @property
    def app_secret(self) -> str:
        return self.app["app_secret"].get()

    async def handler(self, request: Request) -> Response:
        ctx = await request.json()

        logging.debug(ctx)

        if id := request.query.get("id"):
            self.app["app_id"].set(id)

        if secret := request.query.get("secret"):
            self.app["app_secret"].set(secret)

        match ctx["op"]:
            case OP.MESSAGE:
                if not self.session_manager(event := Event(self, ctx)):
                    fire_and_forget(self.plugin_manager(event))

            case OP.VERIFICATION:
                logging.info("webhook verification request received")

                if not (secret := self.app_secret):
                    raise ValueError("parameter `app_secret` must be specified")

                secret = secret.encode("utf-8")

                while len(secret) < 32:
                    secret *= 2

                d = ctx["d"]

                return web.json_response(
                    {
                        "plain_token": d["plain_token"],
                        "signature": (
                            Ed25519PrivateKey.from_private_bytes(secret[:32])
                            .sign(f"{d['event_ts']}{d['plain_token']}".encode("utf-8"))
                            .hex()
                        ),
                    }
                )

            case _:
                logging.warning(f"invalid type received {ctx=}")

        return web.Response(body=None, status=HTTPStatus.OK)

    async def serve(self, *, host="0.0.0.0", port=8080, **kwargs):
        async with self:
            runner = web.AppRunner(self.app, **kwargs)

            try:
                await runner.setup()

                site = web.TCPSite(runner, host, port)

                await site.start()

                await asyncio.Event().wait()

            finally:
                await runner.cleanup()

    def run(self, *, host="0.0.0.0", port=8080, **kwargs):
        asyncio.run(self.serve(host=host, port=port, **kwargs))
