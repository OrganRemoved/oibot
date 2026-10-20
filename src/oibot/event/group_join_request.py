from dataclasses import dataclass, field
from datetime import datetime
from functools import cached_property
from typing import ClassVar, Literal

from oibot.event import Event, EventType


class GroupJoinRequestEvent(Event):
    @dataclass(frozen=True, slots=True)
    class ReviewQA:
        question: str
        answer: str

    @dataclass(frozen=True, slots=True)
    class VerifyInfo:
        method: Literal["verify_message", "admin_review_qa"]
        verify_message: str | None = None
        review_qa_list: list[GroupJoinRequestEvent.ReviewQA] = field(
            default_factory=list
        )

    @dataclass(frozen=True, slots=True)
    class AutoApproved:
        strategy_id: str

    event_type: ClassVar[EventType] = EventType.GROUP_JOIN_REQUEST

    group_openid: str
    join_request_id: str
    risk_tips: str | None
    union_openid: str | None
    member_openid: str
    username: str
    apply_at: datetime
    apply_source: Literal["self_apply", "invited"]
    invited_by: str | None
    is_bot: bool | None
    verify_info: VerifyInfo | None
    auto_approved: AutoApproved | None

    @cached_property
    def apply_at(self) -> datetime:
        return datetime.fromisoformat(self.ctx["d"]["apply_at"])

    @cached_property
    def auto_approved(self) -> AutoApproved | None:
        if auto_approved := self.ctx["d"].get("auto_approved"):
            return self.AutoApproved(strategy_id=auto_approved["strategy_id"])

    @cached_property
    def is_bot(self) -> bool | None:
        return self.ctx["d"].get("bot")

    @cached_property
    def invited_by(self) -> str | None:
        return self.ctx["d"].get("invited_by")

    @cached_property
    def risk_tips(self) -> str | None:
        return self.ctx["d"].get("risk_tips")

    @cached_property
    def union_openid(self) -> str | None:
        return self.ctx["d"].get("union_openid")

    @cached_property
    def verify_info(self) -> VerifyInfo | None:
        if verify_info := self.ctx["d"].get("verify_info"):
            return self.VerifyInfo(
                method=verify_info["method"],
                verify_message=verify_info.get("verify_message"),
                review_qa_list=[
                    self.ReviewQA(
                        question=review_qa["question"], answer=review_qa["answer"]
                    )
                    for review_qa in verify_info.get("review_qa_list", [])
                ],
            )

    async def approve(self) -> None:
        return await self.bot.review_group_join_request(
            group_openid=self.group_openid,
            member_openid=self.member_openid,
            op="approve",
            join_request_id=self.join_request_id,
        )

    async def decline(
        self, *, reject_reason: str | None = None, add_to_member_blacklist: bool = False
    ) -> None:
        return await self.bot.review_group_join_request(
            group_openid=self.group_openid,
            member_openid=self.member_openid,
            op="decline",
            join_request_id=self.join_request_id,
            reject_reason=reject_reason,
            add_to_member_blacklist=add_to_member_blacklist,
        )
