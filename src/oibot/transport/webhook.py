import asyncio
import json
import logging
from enum import IntEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from aiohttp import web
from aiohttp.web_request import Request
from aiohttp.web_response import Response
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from oibot.event import Event

if TYPE_CHECKING:
    from oibot.bot import OiBot


class OpCode(IntEnum):
    DISPATCH = 0
    HTTP_CALLBACK_ACK = 12
    CALLBACK_VALIDATION = 13


class WebhookMixin:
    def __init__(self: OiBot, *, path: str = "/", **kwargs: Any) -> None:
        self.webhook_tasks: set[asyncio.Task[None]] = set()

        self.app.router.add_post(path=path, handler=self.webhook_handler, **kwargs)

    def webhook_run(self: OiBot, *, host: str = "0.0.0.0", port: int = 8080) -> None:
        asyncio.run(WebhookMixin.webhook_serve(self, host=host, port=port))

    async def webhook_serve(
        self: OiBot, *, host: str = "0.0.0.0", port: int = 8080
    ) -> None:
        async with self:
            runner = web.AppRunner(self.app)

            try:
                await runner.setup()

                await web.TCPSite(runner, host, port).start()

                await asyncio.Event().wait()

            finally:
                for task in self.webhook_tasks:
                    task.cancel()

                await asyncio.gather(*self.webhook_tasks, return_exceptions=True)

                await runner.cleanup()

    async def webhook_handler(self: OiBot, request: Request) -> Response:
        body = await request.read()
        ctx = json.loads(body)

        secret = self.app_secret.encode("utf-8")

        while len(secret) < 32:
            secret *= 2

        if ctx["op"] != OpCode.CALLBACK_VALIDATION:
            try:
                Ed25519PrivateKey.from_private_bytes(secret[:32]).public_key().verify(
                    bytes.fromhex(request.headers["X-Signature-Ed25519"]),
                    request.headers["X-Signature-Timestamp"].encode("utf-8") + body,
                )

            except InvalidSignature, KeyError, ValueError:
                logging.warning("rejected webhook request with invalid signature")

                return web.Response(
                    text="invalid webhook signature", status=HTTPStatus.UNAUTHORIZED
                )

        logging.debug(
            f"webhook payload received op={ctx['op']!r} event_type={ctx.get('t')!r}"
        )

        match ctx["op"]:
            case OpCode.DISPATCH:
                event = Event(self, ctx)

                self.quota_pool(event)

                if not self.session_manager(event):
                    self.webhook_tasks.add(
                        task := asyncio.create_task(self.plugin_manager(event))
                    )

                    task.add_done_callback(self.webhook_tasks.discard)

            case OpCode.CALLBACK_VALIDATION:
                logging.info("webhook verification request received")

                return web.json_response(
                    {
                        "plain_token": ctx["d"]["plain_token"],
                        "signature": (
                            Ed25519PrivateKey.from_private_bytes(secret[:32])
                            .sign(
                                f"{ctx['d']['event_ts']}{ctx['d']['plain_token']}".encode()
                            )
                            .hex()
                        ),
                    }
                )

            case _:
                logging.warning("invalid type received op=%r", ctx["op"])

        return web.Response(body=None, status=HTTPStatus.OK)
