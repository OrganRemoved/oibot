from typing import Callable


class Matcher:
    __slots__ = ("rule", "matchers", "operator")

    def __init__(
        self,
        rule: Callable[..., bool] = lambda: True,
        *,
        matchers: list | None = None,
        operator: str | None = None,
    ) -> None:
        self.rule = rule
        self.matchers = matchers or []
        self.operator = operator

    def __call__(self, *args, **kwargs) -> bool:
        match self.operator:
            case "and":
                return all(matcher(*args, **kwargs) for matcher in self.matchers)
            case "or":
                return any(matcher(*args, **kwargs) for matcher in self.matchers)
            case _:
                return self.rule(*args, **kwargs)

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
        return Matcher(rule=lambda *args, **kwargs: not self(*args, **kwargs))
