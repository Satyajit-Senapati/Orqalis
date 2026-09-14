export type TaskStatus =
  | "PENDING"
  | "READY"
  | "RUNNING"
  | "WAITING"
  | "BLOCKED"
  | "SUCCEEDED"
  | "FAILED"
  | "CANCELLED"
  | "SKIPPED";
export interface Timing {
  wall_ms: number;
  active_ms: number;
  waiting_ms: number;
  blocked_ms: number;
  idle_ms: number;
  queue_ms: number;
}
export interface Run {
  id: string;
  project_id: string;
  request: string;
  state: string;
  ui_phase: string;
  target_branch: string;
  base_commit: string;
  created_at: string;
  repair_iteration: number;
  max_repair_iterations: number;
  plan_version: number;
  resume_state: string | null;
  started_at: string | null;
  completed_at: string | null;
}
export interface Task {
  id: string;
  description: string;
  preferred_role: string;
  status: TaskStatus;
  attempt_count: number;
  acceptance_criterion_ids: string[];
  expected_outcome: string;
  required_capabilities: string[];
  expected_artifacts: string[];
  parent_task_id: string | null;
  created_at: string;
  ready_at: string | null;
  started_at: string | null;
  completed_at: string | null;
}
export interface Actor {
  session: {
    id: string;
    actor_type: "ORCHESTRATOR" | "AGENT";
    role: string | null;
    provider: string | null;
    model: string | null;
    status: string;
    current_task_id: string | null;
    loaded_skills: string[];
    started_at: string;
    completed_at: string | null;
    allowed_tools: string[];
    tasks_attempted: number;
    tasks_completed: number;
    tasks_failed: number;
  };
  timing: Timing;
}
export interface Criterion {
  id: string;
  key: string;
  description: string;
  status: "PENDING" | "TESTING" | "PASS" | "FAIL";
  priority: string;
  validation_spec: {
    kind: string;
    argv?: string[];
    path?: string;
    contains?: string;
    instructions?: string;
  };
  evidence_refs: string[];
  attempt_count: number;
}
export interface Event {
  id: string;
  sequence: number;
  event_type: string;
  occurred_at: string;
  task_id: string | null;
  actor_session_id: string | null;
  phase?: string | null;
  status?: string | null;
  payload: {
    status?: string;
    summary?: string;
    reason?: string;
    skill_refs?: string[];
    memory_ids?: string[];
  };
}
export interface Evidence {
  task_execution_id: string | null;
  id: string;
  criterion_id: string;
  task_id: string | null;
  evidence_type: string;
  created_at: string;
  structured_data: {
    passed: boolean;
    error_code: string | null;
    output: string;
    exit_code: number | null;
    source_ref: string | null;
    content_hash: string | null;
    duration_ms: number;
  };
}
export interface Attempt {
  id: string;
  task_id: string;
  assigned_actor_session_id: string;
  attempt: number;
  status: string;
  started_at: string;
  completed_at: string | null;
  queue_ms: number;
}
export interface Segment {
  kind: "actor" | "task" | "phase";
  entity_id: string;
  task_id: string | null;
  status: string;
  started_at: string;
  ended_at: string;
  duration_ms: number;
}
export interface Usage {
  input_tokens: number | null;
  output_tokens: number | null;
  cached_input_tokens: number | null;
  estimated_cost_usd: number | null;
  cost_source: string | null;
}
export interface ProviderCall {
  id: string;
  actor_session_id: string;
  task_execution_id: string;
  provider: string;
  model: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  error_code: string | null;
  usage: Usage | null;
  selected_skills?: string[];
  context_memory_ids?: string[];
  context_summary?: string | null;
}
export interface ToolCall {
  id: string;
  actor_session_id: string;
  task_execution_id: string;
  tool: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  observation: { succeeded: boolean; summary: string } | null;
}
export interface Review {
  id: string;
  plan_version: number;
  created_at: string;
  result: {
    overall: string;
    criteria: {
      criterion_id: string;
      status: string;
      reason: string;
      evidence_refs: string[];
      source_checks: { path: string; contains: string }[];
    }[];
    blocking_findings: string[];
    non_blocking_findings: string[];
  };
}
export interface Finding {
  id: string;
  severity: string;
  category: string;
  summary: string;
  source_ref: string | null;
  status: string;
}
export interface Change {
  path: string;
  status: string;
  added_lines: number;
  deleted_lines: number;
  old_hash: string | null;
  new_hash: string | null;
}
export interface Guardian {
  id: string;
  checkpoint: string;
  passed: boolean;
  changes: Change[];
  findings: Finding[];
  tree_hash: string;
}
export interface Artifact {
  id: string;
  task_id: string | null;
  type: string;
  path_or_uri: string;
  content_hash: string;
}
export interface Stats {
  max_parallel_tasks: number;
  mean_parallel_tasks: number;
  critical_path_task_ids: string[];
  critical_path_working_ms: number;
  provider_calls: number;
  tool_calls: number;
  calls_with_usage: number;
  reported_input_tokens: number | null;
  reported_output_tokens: number | null;
  reported_cached_tokens: number | null;
  reported_cost_usd: number | null;
  calls_with_cost: number;
  first_pass_success: boolean | null;
}
export interface Snapshot {
  skill_activity?: {
    ref: string;
    load_count: number;
    actor_session_ids: string[];
    last_loaded_at: string;
  }[];
  context_memory_ids?: string[];
  tasks: Task[];
  preparation_tasks: Task[];
  run: Run;
  goal: {
    goal: {
      id: string;
      goal: string;
      version: number;
      scope: string[];
      out_of_scope?: string[];
      constraints: string[];
      assumptions?: string[];
      definition_of_done: string[];
    };
    criteria: Criterion[];
  } | null;
  plan: {
    goal_version_id: string;
    version: number;
    tasks: Task[];
    dependencies: { task_id: string; depends_on_task_id: string }[];
  } | null;
  actors: Actor[];
  phases: {
    execution: {
      id: string;
      phase: string;
      iteration: number;
      status: string;
      started_at: string;
      completed_at: string | null;
    };
    timing: Timing;
  }[];
  attempts: Attempt[];
  timing: Timing;
  task_timing: Record<string, Timing>;
  task_counts: Record<TaskStatus, number>;
  plan_completion: number;
  last_event_sequence: number;
  server_time: string;
  evidence: Evidence[];
  timeline: Segment[];
  statistics: Stats;
  providers: ProviderCall[];
  tools: ToolCall[];
  reviews: Review[];
  guardians: Guardian[];
  artifacts: Artifact[];
  findings: Finding[];
  blockers: string[];
  final_validations: {
    id: string;
    passed: boolean;
    tree_hash: string;
    evidence_ids: string[];
  }[];
  delivery: {
    commit_sha: string | null;
    commit_attached: boolean;
    branch: string;
    push_status: string;
    commit_message: string;
    remote: string | null;
  } | null;
}
export interface Project {
  id: string;
  name: string;
  repo_root: string;
  default_branch: string;
}
export interface MemoryMatch {
  item: {
    id: string;
    type: string;
    title: string;
    content: string;
    confidence: number;
    source_commit: string;
    introduced_by_run: string | null;
    last_verified_at: string;
    status: string;
  };
  sources: { source_ref: string; commit_sha: string; content_hash: string }[];
  score: number;
}
export interface Brain {
  project_id: string;
  inspected_root: string;
  query: string;
  freshness: {
    fresh: boolean;
    indexed_commit: string | null;
    current_commit: string;
    dirty_paths: string[];
    active_items: number;
  };
  matches: MemoryMatch[];
  entities: {
    id: string;
    name: string;
    entity_type: string;
    source_refs: string[];
  }[];
  relations: {
    id: string;
    source_entity_id: string;
    target_entity_id: string;
    relation_type: string;
  }[];
}

export interface SkillCatalogEntry {
  metadata: {
    id: string;
    version: string;
    description: string;
    capabilities: string[];
    required_tools: string[];
  };
  source: "bundled" | "configured";
}
