import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from functools import wraps
from typing import TYPE_CHECKING, Any, Concatenate

if TYPE_CHECKING:
    from oibot.bot import OiBot


class CompactDict(dict):
    def __init__(self, **kwargs: Any) -> None:
        super().__init__(
            (key, value) for key, value in kwargs.items() if value is not None
        )


def sliding_window_rate_limit[**P, R](
    *,
    key: str | None = None,
    limit: int = 60,
    window: float | timedelta = timedelta(seconds=60),
) -> Callable[
    [Callable[Concatenate[Any, P], Awaitable[R]]],
    Callable[Concatenate[Any, P], Awaitable[R]],
]:
    if isinstance(window, timedelta):
        window = window.total_seconds()

    def decorator(
        func: Callable[Concatenate[Any, P], Awaitable[R]],
    ) -> Callable[Concatenate[Any, P], Awaitable[R]]:
        slots: dict[Any, set[asyncio.Future[None]]] = {}

        @wraps(func)
        async def wrapper(self: OiBot, *args: P.args, **kwargs: P.kwargs) -> R:
            slot = slots.setdefault(
                (self.app_id, kwargs[key]) if key else self.app_id, set()
            )

            while len(slot) >= limit:
                await asyncio.wait(slot, return_when=asyncio.FIRST_COMPLETED)

            slot.add(future := (loop := asyncio.get_running_loop()).create_future())

            future.add_done_callback(slot.discard)

            loop.call_later(window, future.set_result, None)

            return await func(self, *args, **kwargs)

        return wrapper

    return decorator
