from pathlib import Path
from uuid import uuid4

import pytest

from orqalis.domain.approval import ApprovalStage, ControlMode
from orqalis.mcp.policy import MCPPolicy


def test_operator_owned_mcp_policy_selects_supervised_gates() -> None:
    project_id = uuid4()
    policy = MCPPolicy(
        project_id=project_id,
        workspaces_root=Path("workspaces"),
        control_mode=ControlMode.SUPERVISED,
        approval_gates=frozenset({ApprovalStage.GOAL, ApprovalStage.TASK}),
    )
    assert policy.control_mode == ControlMode.SUPERVISED
    assert policy.approval_gates == frozenset({ApprovalStage.GOAL, ApprovalStage.TASK})
    with pytest.raises(ValueError, match="supervised"):
        MCPPolicy(
            project_id=project_id,
            workspaces_root=Path("workspaces"),
            approval_gates=frozenset({ApprovalStage.TASK}),
        )
