"""Import every mapped table for migration/schema inspection."""

from orqalis.persistence import delivery_models as delivery_models
from orqalis.persistence import execution_models as execution_models
from orqalis.persistence import memory_models as memory_models
from orqalis.persistence import provider_models as provider_models
from orqalis.persistence import runtime_models as runtime_models
from orqalis.persistence import workflow_models as workflow_models
from orqalis.persistence.models import Base as Base
