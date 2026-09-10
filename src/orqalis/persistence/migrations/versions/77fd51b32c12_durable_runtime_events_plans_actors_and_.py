"""durable runtime events plans actors and timing"""

import sqlalchemy as sa
from alembic import op

revision = "77fd51b32c12"
down_revision = "9d45acc139d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "phase_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=False),
        sa.Column("iteration", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("active_ms", sa.Integer(), nullable=False),
        sa.Column("waiting_ms", sa.Integer(), nullable=False),
        sa.Column("blocked_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_phase_executions_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_phase_executions")),
        sa.UniqueConstraint(
            "run_id", "phase", "iteration", name=op.f("uq_phase_executions_run_id")
        ),
    )
    op.create_index(
        op.f("ix_phase_executions_run_id"), "phase_executions", ["run_id"], unique=False
    )
    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("plan_version", sa.Integer(), nullable=False),
        sa.Column("parent_task_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("expected_outcome", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("risk", sa.Float(), nullable=False),
        sa.Column("required_capabilities", sa.JSON(), nullable=False),
        sa.Column("preferred_role", sa.String(length=64), nullable=False),
        sa.Column("expected_artifacts", sa.JSON(), nullable=False),
        sa.Column("validation_method", sa.Text(), nullable=False),
        sa.Column("work_weight", sa.Float(), nullable=False),
        sa.Column("acceptance_criterion_ids", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["parent_task_id"], ["tasks.id"], name=op.f("fk_tasks_parent_task_id_tasks")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_tasks_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tasks")),
    )
    op.create_index(op.f("ix_tasks_run_id"), "tasks", ["run_id"], unique=False)
    op.create_table(
        "actor_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("actor_type", sa.String(length=32), nullable=False),
        sa.Column("role", sa.String(length=64), nullable=True),
        sa.Column("provider", sa.String(length=255), nullable=True),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("current_task_id", sa.Uuid(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("working_ms", sa.Integer(), nullable=False),
        sa.Column("waiting_ms", sa.Integer(), nullable=False),
        sa.Column("blocked_ms", sa.Integer(), nullable=False),
        sa.Column("tasks_attempted", sa.Integer(), nullable=False),
        sa.Column("tasks_completed", sa.Integer(), nullable=False),
        sa.Column("tasks_failed", sa.Integer(), nullable=False),
        sa.Column("loaded_skills", sa.JSON(), nullable=False),
        sa.Column("allowed_tools", sa.JSON(), nullable=False),
        sa.Column("activity_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["current_task_id"], ["tasks.id"], name=op.f("fk_actor_sessions_current_task_id_tasks")
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_actor_sessions_run_id_runs")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_actor_sessions")),
    )
    op.create_index(op.f("ix_actor_sessions_run_id"), "actor_sessions", ["run_id"], unique=False)
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("goal_version_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["goal_version_id"],
            ["goal_versions.id"],
            name=op.f("fk_plans_goal_version_id_goal_versions"),
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_plans_run_id_runs")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_plans")),
        sa.UniqueConstraint("run_id", "version", name=op.f("uq_plans_run_id")),
    )
    op.create_index(op.f("ix_plans_run_id"), "plans", ["run_id"], unique=False)
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("depends_on_task_id", sa.Uuid(), nullable=False),
        sa.Column("dependency_type", sa.String(length=32), nullable=False),
        sa.ForeignKeyConstraint(
            ["depends_on_task_id"],
            ["tasks.id"],
            name=op.f("fk_task_dependencies_depends_on_task_id_tasks"),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_dependencies_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("task_id", "depends_on_task_id", name=op.f("pk_task_dependencies")),
    )
    op.create_table(
        "task_executions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("task_id", sa.Uuid(), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("assigned_actor_session_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("queue_ms", sa.Integer(), nullable=False),
        sa.Column("active_ms", sa.Integer(), nullable=False),
        sa.Column("waiting_ms", sa.Integer(), nullable=False),
        sa.Column("blocked_ms", sa.Integer(), nullable=False),
        sa.Column("result_ref", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["assigned_actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_task_executions_assigned_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["runs.id"], name=op.f("fk_task_executions_run_id_runs")
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name=op.f("fk_task_executions_task_id_tasks")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_task_executions")),
        sa.UniqueConstraint("task_id", "attempt", name=op.f("uq_task_executions_task_id")),
    )
    op.create_index(op.f("ix_task_executions_run_id"), "task_executions", ["run_id"], unique=False)
    op.create_index(
        op.f("ix_task_executions_task_id"), "task_executions", ["task_id"], unique=False
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("phase", sa.String(length=32), nullable=True),
        sa.Column("task_id", sa.Uuid(), nullable=True),
        sa.Column("task_execution_id", sa.Uuid(), nullable=True),
        sa.Column("actor_session_id", sa.Uuid(), nullable=True),
        sa.Column("correlation_id", sa.Uuid(), nullable=True),
        sa.Column("causation_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["actor_session_id"],
            ["actor_sessions.id"],
            name=op.f("fk_events_actor_session_id_actor_sessions"),
        ),
        sa.ForeignKeyConstraint(
            ["causation_id"], ["events.id"], name=op.f("fk_events_causation_id_events")
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], name=op.f("fk_events_project_id_projects")
        ),
        sa.ForeignKeyConstraint(["run_id"], ["runs.id"], name=op.f("fk_events_run_id_runs")),
        sa.ForeignKeyConstraint(
            ["task_execution_id"],
            ["task_executions.id"],
            name=op.f("fk_events_task_execution_id_task_executions"),
        ),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], name=op.f("fk_events_task_id_tasks")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_events")),
        sa.UniqueConstraint("run_id", "idempotency_key", name="uq_events_run_idempotency"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_events_run_sequence"),
    )
    op.create_index(op.f("ix_events_project_id"), "events", ["project_id"], unique=False)
    op.create_index(op.f("ix_events_run_id"), "events", ["run_id"], unique=False)
    op.add_column(
        "runs", sa.Column("plan_version", sa.Integer(), server_default="0", nullable=False)
    )
    op.alter_column("runs", "plan_version", server_default=None)
    op.add_column("runs", sa.Column("resume_state", sa.String(length=64), nullable=True))

    op.execute("""
        CREATE FUNCTION orqalis_deny_event_mutation() RETURNS trigger
        LANGUAGE plpgsql AS $$ BEGIN
          RAISE EXCEPTION 'Orqalis events are append-only';
        END; $$;
    """)
    op.execute("""
        CREATE TRIGGER events_append_only BEFORE UPDATE OR DELETE ON events
        FOR EACH ROW EXECUTE FUNCTION orqalis_deny_event_mutation();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER events_append_only ON events")
    op.execute("DROP FUNCTION orqalis_deny_event_mutation()")
    op.drop_column("runs", "resume_state")
    op.drop_column("runs", "plan_version")
    op.drop_index(op.f("ix_events_run_id"), table_name="events")
    op.drop_index(op.f("ix_events_project_id"), table_name="events")
    op.drop_table("events")
    op.drop_index(op.f("ix_task_executions_task_id"), table_name="task_executions")
    op.drop_index(op.f("ix_task_executions_run_id"), table_name="task_executions")
    op.drop_table("task_executions")
    op.drop_table("task_dependencies")
    op.drop_index(op.f("ix_plans_run_id"), table_name="plans")
    op.drop_table("plans")
    op.drop_index(op.f("ix_actor_sessions_run_id"), table_name="actor_sessions")
    op.drop_table("actor_sessions")
    op.drop_index(op.f("ix_tasks_run_id"), table_name="tasks")
    op.drop_table("tasks")
    op.drop_index(op.f("ix_phase_executions_run_id"), table_name="phase_executions")
    op.drop_table("phase_executions")
