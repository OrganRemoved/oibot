import asyncio
import logging
from contextvars import ContextVar
from enum import IntEnum
from http import HTTPStatus
from os import environ
from typing import Any, Iterable, Literal, NamedTuple, Optional

from aiohttp import ClientSession, web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.mixin.access_token import AccessTokenMixin
from oibot.mixin.recall_message import RecallMessageMixin
from oibot.mixin.send_message import SendMessageMixin
from oibot.mixin.upload_file import UploadFileMixin


class OP(IntEnum):
    MESSAGE = 0
    VERIFICATION = 13


class Bot(NamedTuple):
    app_id: str
    app_token: str
    app_secret: str


class Singleton(type):
    instance: Optional["OiBot"] = None

    def __call__(cls, *args, **kwargs) -> "OiBot":
        if not (instance := cls.instance):
            cls.instance = instance = super().__call__(*args, **kwargs)

        return instance


class OiBot(
    AccessTokenMixin,
    RecallMessageMixin,
    SendMessageMixin,
    UploadFileMixin,
    metaclass=Singleton,
):
    __slots__ = ("app", "plugin_manager", "bot")

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

        self.bot: ContextVar[Bot] = ContextVar("bot")

    async def __call__(
        self,
        method: Literal[
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "PATCH",
            "HEAD",
            "OPTIONS",
            "TRACE",
            "CONNECT",
        ],
        url: str,
        **kwargs,
    ) -> Any:
        logging.debug(f"{method=} {url=} {kwargs=}")

        async with ClientSession(
            base_url="https://api.sgroup.qq.com",  # "https://sandbox.api.sgroup.qq.com"
        ) as session:
            async with session.request(method, url, **kwargs) as resp:
                resp.raise_for_status()

                return await resp.json()

    async def handler(
        self, request: Request, *, background_tasks: set[asyncio.Task] = set()
    ) -> Response:
        ctx = await request.json()

        logging.debug(ctx)

        self.bot.set(
            bot := Bot(
                app_id=request.query.get("id", environ["OIBOT_APP_ID"]),
                app_token=request.query.get("token", environ["OIBOT_APP_TOKEN"]),
                app_secret=request.query.get("secret", environ["OIBOT_APP_SECRET"]),
            )
        )

        match ctx["op"]:
            case OP.MESSAGE:
                background_tasks.add(
                    task := asyncio.create_task(self.plugin_manager(ctx))
                )

                task.add_done_callback(background_tasks.discard)

            case OP.VERIFICATION:
                logging.info("webhook verification request received")

                if not (secret := bot.app_secret):
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
