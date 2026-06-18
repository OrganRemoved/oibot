import json
import logging
from contextlib import AsyncExitStack, asynccontextmanager, contextmanager
from contextvars import ContextVar
from enum import IntEnum
from http import HTTPMethod, HTTPStatus
from inspect import isasyncgenfunction, isgeneratorfunction
from os import environ
from typing import Any, AsyncIterator, Iterable

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.api.access_token import AccessTokenMixin
from oibot.api.interaction import InteractionMixin
from oibot.api.recall_message import DeleteMessageMixin
from oibot.api.send_message import SendMessageMixin
from oibot.api.upload_file import UploadFileMixin
from oibot.matcher import ensure_async, fire_and_forget


class OP(IntEnum):
    MESSAGE = 0
    VERIFICATION = 13


class Singleton(type):
    def __call__(cls, *args, **kwargs) -> "OiBot":
        if not (instance := getattr(cls, "instance", None)):
            cls.instance = instance = super().__call__(*args, **kwargs)

        return instance


class OiBot(
    AccessTokenMixin,
    InteractionMixin,
    DeleteMessageMixin,
    SendMessageMixin,
    UploadFileMixin,
    metaclass=Singleton,
):
    __slots__ = ("app", "plugin_manager")

    def __init__(self, plugins: str | Iterable[str] | None = None, **kwargs) -> None:
        from oibot.plugin import PluginManager

        self.plugin_manager = plugin_manager = PluginManager(self)

        if isinstance(plugins, str):
            plugin_manager.import_from(plugins)

        elif isinstance(plugins, Iterable):
            for plugin in plugins:
                plugin_manager.import_from(plugin)

        self.app = app = web.Application(**kwargs)

        app.router.add_post(path="/", handler=self.handler)

        app["app_id"] = ContextVar("app_id")
        app["app_secret"] = ContextVar("app_secret")

        async def aiohttp_ctx(app: web.Application) -> AsyncIterator[None]:
            async with ClientSession(base_url="https://api.sgroup.qq.com") as session:
                app["session"] = session

                yield

        app.cleanup_ctx.append(aiohttp_ctx)

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

    async def __call__(self, method: HTTPMethod, url: str, **kwargs) -> Any:
        logging.debug(f"{method=} {url=} {kwargs=}")

        async with self.app["session"].request(method, url, **kwargs) as resp:
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

        self.app["app_id"].set(request.query.get("id") or environ["OIBOT_APP_ID"])
        self.app["app_secret"].set(
            request.query.get("secret") or environ["OIBOT_APP_SECRET"]
        )

        match ctx["op"]:
            case OP.MESSAGE:
                fire_and_forget(self.plugin_manager(ctx))

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

    def run(self, *args, **kwargs) -> None:
        web.run_app(self.app, *args, **kwargs)
