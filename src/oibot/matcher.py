import asyncio
from collections.abc import Awaitable, Callable, Coroutine
from functools import reduce, wraps
from inspect import iscoroutinefunction
from operator import and_, or_
from typing import Any, overload


@overload
def ensure_async[**P, R](
    func: Callable[P, Coroutine[Any, Any, R]], *, to_thread: bool = False
) -> Callable[P, Awaitable[R]]: ...


@overload
def ensure_async[**P, R](
    func: Callable[P, R], *, to_thread: bool = False
) -> Callable[P, Awaitable[R]]: ...


@overload
def ensure_async(
    func: None = None, *, to_thread: bool = False
) -> Callable[[Callable[..., Any]], Callable[..., Awaitable[Any]]]: ...


def ensure_async(
    func: Callable[..., Any] | None = None, *, to_thread: bool = False
) -> (
    Callable[..., Awaitable[Any]]
    | Callable[[Callable[..., Any]], Callable[..., Awaitable[Any]]]
):
    if func is None:

        def decorator(func: Callable[..., Any]) -> Callable[..., Awaitable[Any]]:
            return ensure_async(func, to_thread=to_thread)

        return decorator

    if iscoroutinefunction(func):
        return func

    if to_thread:

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await asyncio.to_thread(func, *args, **kwargs)
    else:

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

    return wrapper


class Matcher[**P]:
    __slots__ = ("awaitable", "matchers", "operator", "rule")

    def __init__(
        self,
        rule: Callable[P, Any] = lambda *args, **kwargs: True,
        *,
        awaitable: bool = False,
        matchers: list[Matcher[P]] | None = None,
        operator: Callable[[Matcher[P], Matcher[P]], Matcher[P]] | None = None,
    ) -> None:
        self.rule = rule

        self.awaitable = (
            awaitable
            or iscoroutinefunction(self.__call__)
            or iscoroutinefunction(rule)
            or iscoroutinefunction(rule.__call__)
        )

        self.matchers = matchers or []
        self.operator = operator

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Any:
        return self.rule(*args, **kwargs)

    def __and__(self, other: Matcher[P]) -> Matcher[P]:
        matchers = [
            *(self.matchers if self.operator is and_ else [self]),
            *(other.matchers if other.operator is and_ else [other]),
        ]

        sync_matchers = [matcher for matcher in matchers if not matcher.awaitable]

        if async_matchers := [matcher for matcher in matchers if matcher.awaitable]:

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                ctx = {}

                for matcher in sync_matchers:
                    if not (matched := matcher(*args, **kwargs)):
                        return {}

                    ctx |= matched if isinstance(matched, dict) else {"_": matched}

                try:
                    async for completed_task in asyncio.as_completed(
                        tasks := [
                            asyncio.create_task(matcher(*args, **kwargs))
                            for matcher in async_matchers
                        ]
                    ):
                        if not (matched := await completed_task):
                            return {}

                        ctx |= matched if isinstance(matched, dict) else {"_": matched}

                finally:
                    pending = [task for task in tasks if not task.done()]

                    for task in pending:
                        task.cancel()

                    await asyncio.gather(*pending, return_exceptions=True)

                return ctx

        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                ctx = {}

                for matcher in sync_matchers:
                    if not (matched := matcher(*args, **kwargs)):
                        return {}

                    ctx |= matched if isinstance(matched, dict) else {"_": matched}

                return ctx

        return Matcher(
            rule=wrapper,
            awaitable=bool(async_matchers),
            matchers=matchers,
            operator=and_,
        )

    def __or__(self, other: Matcher[P]) -> Matcher[P]:
        matchers = [
            *(self.matchers if self.operator is or_ else [self]),
            *(other.matchers if other.operator is or_ else [other]),
        ]

        sync_matchers = [matcher for matcher in matchers if not matcher.awaitable]

        if async_matchers := [matcher for matcher in matchers if matcher.awaitable]:

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                for matcher in sync_matchers:
                    if matched := matcher(*args, **kwargs):
                        return matched if isinstance(matched, dict) else {"_": matched}

                try:
                    async for completed_task in asyncio.as_completed(
                        tasks := [
                            asyncio.create_task(matcher(*args, **kwargs))
                            for matcher in async_matchers
                        ]
                    ):
                        if matched := await completed_task:
                            return (
                                matched if isinstance(matched, dict) else {"_": matched}
                            )

                finally:
                    pending = [task for task in tasks if not task.done()]

                    for task in pending:
                        task.cancel()

                    await asyncio.gather(*pending, return_exceptions=True)

                return {}
        else:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
                for matcher in sync_matchers:
                    if matched := matcher(*args, **kwargs):
                        return matched if isinstance(matched, dict) else {"_": matched}

                return {}

        return Matcher(
            rule=wrapper,
            awaitable=bool(async_matchers),
            matchers=matchers,
            operator=or_,
        )

    def __invert__(self) -> Matcher[P]:
        if not self.awaitable:

            def wrapper(*args: P.args, **kwargs: P.kwargs) -> bool:
                return not self(*args, **kwargs)

        else:

            async def wrapper(*args: P.args, **kwargs: P.kwargs) -> bool:
                return not await self(*args, **kwargs)

        return Matcher(rule=wrapper, awaitable=self.awaitable)

    async def match(self, *args: P.args, **kwargs: P.kwargs) -> dict[str, Any]:
        if matched := (
            await self(*args, **kwargs) if self.awaitable else self(*args, **kwargs)
        ):
            return matched if isinstance(matched, dict) else {"_": matched}

        return {}

    @classmethod
    def all(cls, *matchers: Matcher[P]) -> Matcher[P]:
        return reduce(and_, matchers)

    @classmethod
    def any(cls, *matchers: Matcher[P]) -> Matcher[P]:
        return reduce(or_, matchers)
