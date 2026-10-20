from datetime import timedelta
from http import HTTPMethod
from typing import TYPE_CHECKING, Literal, NotRequired, TypedDict

from oibot.api import CompactDict, sliding_window_rate_limit

if TYPE_CHECKING:
    from oibot.bot import OiBot


class BotState(TypedDict):
    member_openid: str
    joined_at: str
    allow_proactive_msg: bool
    recv_msg_setting: Literal["all", "only_mention", "mention_and_context"]
    member_role: Literal["member", "owner", "admin"]


class GroupInformation(TypedDict):
    group_openid: str
    group_name: str
    group_finger_memo: str
    group_class_text: str
    group_tags: list[str]
    group_member_num: int


class GroupMember(TypedDict):
    member_openid: str
    username: str
    member_role: Literal["member", "owner", "admin"]
    bot: bool
    joined_at: str
    union_openid: NotRequired[str]


class GroupMemberListResponse(TypedDict):
    members: list[GroupMember]
    next_cursor: str


class BatchRemoveGroupMembersResponse(TypedDict):
    remove_members_result: Literal["success"]
    add_to_member_blacklist_fail_openids: list[str]


class GroupMemberBlacklistUser(TypedDict):
    union_openid: NotRequired[str]
    member_openid: str
    username: str
    banned_at: str
    bot: bool


class GroupMemberBlacklistResponse(TypedDict):
    users: list[GroupMemberBlacklistUser]
    next_cursor: str


class UpdateGroupMemberBlacklistResponse(TypedDict):
    fail_openids: list[str]


class ReviewQA(TypedDict):
    question: str
    answer: str


class VerifyInfo(TypedDict):
    method: Literal["verify_message", "admin_review_qa"]
    verify_message: NotRequired[str]
    review_qa_list: NotRequired[list[ReviewQA]]


class JoinRequest(TypedDict):
    join_request_id: str
    risk_tips: str
    union_openid: NotRequired[str]
    member_openid: str
    username: str
    apply_at: str
    apply_source: Literal["self_apply", "invited"]
    invited_by: NotRequired[str]
    bot: bool
    verify_info: NotRequired[VerifyInfo]


class JoinRequestListResponse(TypedDict):
    list: list[JoinRequest]
    next_cursor: str


class MuteScheduleRule(TypedDict):
    task_id: str
    start_at: str
    end_at: str
    enabled: bool


class MuteRecurringRule(TypedDict):
    task_id: str
    weekdays: list[Literal[1, 2, 3, 4, 5, 6, 7]]
    start_time: str
    end_time: str
    enabled: bool


class GlobalMuteRule(TypedDict):
    mode: Literal["none", "always", "schedule"]
    schedule_rules: list[MuteScheduleRule]
    recurring_rules: list[MuteRecurringRule]


class MemberMuteState(TypedDict):
    member_openid: str
    mute_expire_at: str
    username: str
    union_openid: NotRequired[str]


class RestrictChatSetting(TypedDict):
    global_rule: GlobalMuteRule
    members: list[MemberMuteState]


class SetMemberMuteState(TypedDict):
    op: Literal["add", "update", "del"]
    member_openid: str
    mute_expire_at: NotRequired[str]


class GroupJoinApprovalStrategy(TypedDict):
    strategy_id: str
    group_openids: list[str]
    group_ids: list[int]
    whitelist_user_count: int
    is_enable: Literal["on", "off"]
    expire_at: str
    created_at: str
    updated_at: str
    remark: NotRequired[str]


class GroupJoinApprovalStrategyListResponse(TypedDict):
    strategies: list[GroupJoinApprovalStrategy]
    next_cursor: str


class CreateGroupJoinApprovalStrategyResponse(TypedDict):
    strategy_id: str
    is_enable: Literal["on", "off"]
    expire_at: str


class GroupJoinApprovalStrategyGroupAction(TypedDict):
    op: Literal["add", "del"]
    group_openids: NotRequired[list[str]]
    group_ids: NotRequired[list[int]]


class UpdateGroupJoinApprovalStrategyResponse(TypedDict):
    is_enable: Literal["on", "off"]
    expire_at: str


class UpdateGroupJoinApprovalStrategyWhitelistResponse(TypedDict):
    strategy_id: str
    whitelist_user_count: int
    updated_at: str


class GroupManagementMixin:
    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_info(self: OiBot, *, group_openid: str) -> GroupInformation:
        return await self(HTTPMethod.GET, f"/v2/groups/{group_openid}/info")

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_bot_state(self: OiBot, *, group_openid: str) -> BotState:
        return await self(HTTPMethod.GET, f"/v2/groups/{group_openid}/bot_state")

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def get_group_members(
        self: OiBot, *, group_openid: str, cursor: str | None = None
    ) -> GroupMemberListResponse:
        return await self(
            HTTPMethod.GET,
            f"/v2/groups/{group_openid}/members",
            params=CompactDict(cursor=cursor),
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_member(
        self: OiBot, *, group_openid: str, member_openid: str
    ) -> GroupMember:
        return await self(
            HTTPMethod.GET, f"/v2/groups/{group_openid}/members/{member_openid}"
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def remove_group_members(
        self: OiBot,
        *,
        group_openid: str,
        member_openids: list[str],
        add_to_member_blacklist: bool = False,
    ) -> BatchRemoveGroupMembersResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/batch_remove_members",
            json={
                "member_openids": member_openids,
                "add_to_member_blacklist": add_to_member_blacklist,
            },
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_join_requests(
        self: OiBot,
        *,
        group_openid: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> JoinRequestListResponse:
        return await self(
            HTTPMethod.GET,
            f"/v2/groups/{group_openid}/join_request_list",
            json=CompactDict(cursor=cursor, limit=limit),
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def review_group_join_request(
        self: OiBot,
        *,
        group_openid: str,
        member_openid: str,
        op: Literal["approve", "decline"],
        join_request_id: str | None = None,
        reject_reason: str | None = None,
        add_to_member_blacklist: bool = False,
    ) -> None:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/approval_join_request/{member_openid}",
            json=CompactDict(
                op=op,
                join_request_id=join_request_id,
                reject_reason=reject_reason,
                add_to_member_blacklist=add_to_member_blacklist,
            ),
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_member_blacklist(
        self: OiBot,
        *,
        group_openid: str,
        cursor: str | None = None,
        limit: int | None = None,
    ) -> GroupMemberBlacklistResponse:
        return await self(
            HTTPMethod.GET,
            f"/v2/groups/{group_openid}/member_blacklist",
            params=CompactDict(cursor=cursor, limit=limit),
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def update_group_member_blacklist(
        self: OiBot,
        *,
        group_openid: str,
        op: Literal["add", "del"],
        member_openids: list[str],
    ) -> UpdateGroupMemberBlacklistResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/member_blacklist",
            json={"op": op, "member_openids": member_openids},
        )

    @sliding_window_rate_limit(limit=30, window=timedelta(minutes=1))
    async def get_group_restrict_chat_setting(
        self: OiBot, *, group_openid: str
    ) -> RestrictChatSetting:
        return await self(
            HTTPMethod.GET, f"/v2/groups/{group_openid}/restrict_chat_setting"
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def set_group_restrict_chat_setting(
        self: OiBot,
        *,
        group_openid: str,
        members: list[SetMemberMuteState] | None = None,
    ) -> None:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/{group_openid}/restrict_chat_setting",
            json=CompactDict(members=members),
        )


class GroupJoinApprovalStrategyMixin:
    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def get_group_join_approval_strategies(
        self: OiBot, *, cursor: str | None = None, limit: int | None = None
    ) -> GroupJoinApprovalStrategyListResponse:
        return await self(
            HTTPMethod.GET,
            "/v2/groups/join_approval_strategy",
            json=CompactDict(cursor=cursor, limit=limit),
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def create_group_join_approval_strategy(
        self: OiBot,
        *,
        group_openids: list[str] | None = None,
        group_ids: list[int] | None = None,
        is_enable: Literal["on", "off"] | None = None,
        expire_at: str | None = None,
        remark: str | None = None,
    ) -> CreateGroupJoinApprovalStrategyResponse:
        return await self(
            HTTPMethod.POST,
            "/v2/groups/join_approval_strategy",
            json=CompactDict(
                group_openids=group_openids,
                group_ids=group_ids,
                is_enable=is_enable,
                expire_at=expire_at,
                remark=remark,
            ),
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def update_group_join_approval_strategy(
        self: OiBot,
        *,
        strategy_id: str,
        is_enable: Literal["on", "off"] | None = None,
        expire_at: str | None = None,
        group_action: GroupJoinApprovalStrategyGroupAction | None = None,
        remark: str | None = None,
    ) -> UpdateGroupJoinApprovalStrategyResponse:
        return await self(
            HTTPMethod.PATCH,
            f"/v2/groups/join_approval_strategy/{strategy_id}",
            json=CompactDict(
                is_enable=is_enable,
                expire_at=expire_at,
                group_action=group_action,
                remark=remark,
            ),
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def delete_group_join_approval_strategy(
        self: OiBot, *, strategy_id: str
    ) -> None:
        return await self(
            HTTPMethod.DELETE, f"/v2/groups/join_approval_strategy/{strategy_id}"
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def execute_group_join_approval_strategy(
        self: OiBot, *, strategy_id: str
    ) -> None:
        return await self(
            HTTPMethod.POST, f"/v2/groups/join_approval_strategy/{strategy_id}/execute"
        )

    @sliding_window_rate_limit(limit=60, window=timedelta(minutes=1))
    async def update_group_join_approval_strategy_whitelist_users(
        self: OiBot,
        *,
        strategy_id: str,
        op: Literal["add", "del"],
        whitelist_users: list[str],
    ) -> UpdateGroupJoinApprovalStrategyWhitelistResponse:
        return await self(
            HTTPMethod.POST,
            f"/v2/groups/join_approval_strategy/{strategy_id}/whitelist_users",
            json={"op": op, "whitelist_users": whitelist_users},
        )
