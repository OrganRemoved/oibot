import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, Literal


def ensure_async(func: Callable[..., Any], *, to_thread: bool = False) -> Any:
    if to_thread:

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return await asyncio.to_thread(func, *args, **kwargs)
    else:

        @wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            return func(*args, **kwargs)

    return wrapper


class Matcher:
    __slots__ = ("rule", "matchers", "operator")

    def __init__(
        self,
        rule: Callable[..., bool | Awaitable[bool]] = lambda *args, **kwargs: True,
        *,
        matchers: list["Matcher"] | None = None,
        operator: Literal["and", "or"] | None = None,
        to_thread: bool = False,
    ) -> None:
        self.rule = (
            rule
            if asyncio.iscoroutinefunction(rule)
            else ensure_async(rule, to_thread=to_thread)
        )

        self.matchers = matchers or []
        self.operator = operator

    async def __call__(self, *args, **kwargs) -> bool:
        match self.operator:
            case "and":
                tasks = [
                    asyncio.create_task(matcher(*args, **kwargs))
                    for matcher in self.matchers
                ]

                async for completed_task in asyncio.as_completed(tasks):
                    if not await completed_task:
                        for task in tasks:
                            if not task.done() and not task.cancelled():
                                task.cancel()

                        return False

                return True

            case "or":
                tasks = [
                    asyncio.create_task(matcher(*args, **kwargs))
                    for matcher in self.matchers
                ]

                async for completed_task in asyncio.as_completed(tasks):
                    if await completed_task:
                        for task in tasks:
                            if not task.done() and not task.cancelled():
                                task.cancel()

                        return True

                return False

            case _:
                return await self.rule(*args, **kwargs)

    def __and__(self, other: "Matcher") -> "Matcher":
        if self.operator == "and":
            self.matchers.append(other)
            return self

        return Matcher(matchers=[self, other], operator="and")

    def __or__(self, other: "Matcher") -> "Matcher":
        if self.operator == "or":
            self.matchers.append(other)
            return self

        return Matcher(matchers=[self, other], operator="or")

    def __invert__(self) -> "Matcher":
        async def wrapper(*args, **kwargs) -> bool:
            return not await self(*args, **kwargs)

        return Matcher(rule=wrapper)
