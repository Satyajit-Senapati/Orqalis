from pathlib import Path
from typing import Self
from uuid import UUID

from pydantic import model_validator

from orqalis.domain.approval import ApprovalStage, ControlMode
from orqalis.domain.base import Contract
from orqalis.domain.delivery import DeliveryPolicy
from orqalis.domain.errors import PolicyDeniedError
from orqalis.domain.execution import ExecutionPolicy


class MCPPolicy(Contract):
    project_id: UUID
    workspaces_root: Path
    allow_work: bool = False
    allow_delivery: bool = False
    execution: ExecutionPolicy | None = None
    delivery: DeliveryPolicy | None = None
    reviewer_provider: str = "openai"
    control_mode: ControlMode = ControlMode.AUTONOMOUS
    approval_gates: frozenset[ApprovalStage] | None = None

    @model_validator(mode="after")
    def coherent(self) -> Self:
        if self.control_mode == ControlMode.AUTONOMOUS and self.approval_gates:
            raise ValueError("Custom approval gates require supervised control mode")
        if self.allow_work and self.execution is None:
            raise ValueError("Work permission requires a server-approved execution policy")
        if self.allow_delivery and (not self.allow_work or self.delivery is None):
            raise ValueError("Delivery permission requires work and an explicit delivery policy")
        return self

    def require_work(self) -> ExecutionPolicy:
        if not self.allow_work or self.execution is None:
            raise PolicyDeniedError("This MCP server is read-only")
        return self.execution

    def require_delivery(self) -> DeliveryPolicy:
        if not self.allow_delivery or self.delivery is None:
            raise PolicyDeniedError("Delivery is not enabled on this MCP server")
        return self.delivery
