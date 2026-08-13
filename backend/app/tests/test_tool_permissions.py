import dataclasses

import pytest

from app.services.ai.tools.base_tool import BaseTool
from app.services.ai.tools.context import ToolContext
from app.services.ai.tools.enums import ToolCapability, ToolCategory, ToolPermission
from app.services.ai.tools.permissions import PermissionPolicy, missing_permissions
from app.services.ai.tools.result import ToolResult
from app.services.ai.tools.schema import ToolSchema


class _FakeTool(BaseTool):
    def __init__(self, permissions=()):
        self._permissions = frozenset(permissions)

    @property
    def tool_id(self) -> str:
        return "fake-tool"

    @property
    def name(self) -> str:
        return "Fake Tool"

    @property
    def description(self) -> str:
        return ""

    @property
    def version(self) -> str:
        return "1.0"

    @property
    def category(self) -> ToolCategory:
        return ToolCategory.CUSTOM_BUSINESS

    @property
    def capabilities(self) -> frozenset[ToolCapability]:
        return frozenset()

    @property
    def permissions(self) -> frozenset[ToolPermission]:
        return self._permissions

    def input_schema(self) -> ToolSchema:
        return ToolSchema()

    def output_schema(self) -> ToolSchema:
        return ToolSchema()

    def validate(self, parameters) -> None:
        return None

    def execute(self, context: ToolContext) -> ToolResult:
        return ToolResult(success=True)

    def health_check(self) -> bool:
        return True


def test_permission_policy_defaults():
    policy = PermissionPolicy()

    assert policy.granted_permissions == frozenset()
    assert policy.allow_all is False
    assert policy.deny_all is False


def test_granted_permissions_is_coerced_to_a_frozenset():
    policy = PermissionPolicy(granted_permissions=[ToolPermission.NETWORK])

    assert isinstance(policy.granted_permissions, frozenset)


def test_is_frozen():
    policy = PermissionPolicy()

    with pytest.raises(dataclasses.FrozenInstanceError):
        policy.allow_all = True


# --- missing_permissions ---------------------------------------------------------------


def test_no_permissions_required_means_nothing_missing():
    tool = _FakeTool(permissions=())

    assert missing_permissions(tool, PermissionPolicy()) == frozenset()


def test_ungranted_permission_is_reported_missing():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))

    assert missing_permissions(tool, PermissionPolicy()) == {ToolPermission.NETWORK}


def test_granted_permission_is_not_missing():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))
    policy = PermissionPolicy(granted_permissions={ToolPermission.NETWORK})

    assert missing_permissions(tool, policy) == frozenset()


def test_allow_all_means_nothing_is_ever_missing():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK, ToolPermission.SHELL_EXECUTE))
    policy = PermissionPolicy(allow_all=True)

    assert missing_permissions(tool, policy) == frozenset()


def test_deny_all_means_every_required_permission_is_missing():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK,))
    policy = PermissionPolicy(deny_all=True, granted_permissions={ToolPermission.NETWORK})

    assert missing_permissions(tool, policy) == {ToolPermission.NETWORK}


def test_partial_grant_reports_only_the_ungranted_ones():
    tool = _FakeTool(permissions=(ToolPermission.NETWORK, ToolPermission.SHELL_EXECUTE))
    policy = PermissionPolicy(granted_permissions={ToolPermission.NETWORK})

    assert missing_permissions(tool, policy) == {ToolPermission.SHELL_EXECUTE}
