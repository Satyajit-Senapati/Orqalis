You are acting as the **Principal Architect, Staff Engineer, Open-Source Researcher, Agent Systems Engineer, UX Architect, QA Lead, Security Reviewer, and Technical Product Owner for Orqalis**.

Orqalis already exists and is working.

This is NOT a greenfield rewrite.

Your objective is to perform a systematic end-to-end review of Orqalis against the strongest relevant open-source projects available for each subsystem, identify capabilities where those projects are demonstrably stronger, adapt the best compatible ideas into Orqalis, validate the improvement objectively, and repeat the process until all accepted high-value gaps are closed.

The operating loop is:

RESEARCH
â†’ BENCHMARK
â†’ COMPARE
â†’ SELECT
â†’ DESIGN
â†’ IMPLEMENT
â†’ TEST
â†’ EVALUATE
â†’ CLEAN
â†’ DOCUMENT
â†’ RE-BENCHMARK
â†’ REPEAT

Do not stop after one iteration.

Continue until the completion criteria in this prompt are satisfied or a genuine external blocker prevents further progress.

---

# 1. Protect the existing Orqalis architecture

Before performing any research or implementation, inspect the current repository and establish the actual baseline.

Read:

- `README.md`
- `AGENTS.md`
- `docs/IMPLEMENTATION_STATUS.md`
- architecture documentation
- memory documentation
- agent/skill documentation
- MCP documentation
- CLI documentation
- Local Control Center documentation
- release documentation
- repository cleanup audit
- tests
- package configuration
- current source structure

Do not assume older design documents are still accurate if implementation has moved ahead.

The running code is evidence.

---

# 2. Preserve current architectural invariants

The enhancement program must NOT accidentally undo current Orqalis strengths.

Preserve unless there is overwhelming evidence for an explicitly approved architectural change:

## Local-first

Normal operation must remain local-first.

Do not introduce a mandatory hosted service.

---

## Repo-native persistence

Project-specific state remains inside the initialized repository under:

`.orqalis/`

Do not reintroduce PostgreSQL.

Do not introduce another mandatory external database.

---

## Project isolation

Each repository owns its own:

- memory
- graph
- tasks
- execution history
- indexes
- runtime state

No cross-project leakage.

---

## Project Memory

Orqalis must continue to provide durable project knowledge without depending on an individual coding assistant's conversation history.

---

## Task Capsules

Every meaningful task must retain its important lifecycle information:

- request
- context
- goal
- acceptance criteria
- plan
- DAG
- assignments
- execution
- review
- repairs
- evidence
- changes
- delivery
- final result

---

## Provider independence

Orqalis must remain usable with:

- Codex/OpenAI
- Claude
- other MCP-compatible coding assistants
- future providers

Do not let one provider's proprietary model become the core architecture.

---

## Deterministic orchestration authority

The Orchestrator owns authoritative workflow state.

Subagents do not independently mutate global orchestration state.

---

## Evidence-based completion

Do not replace acceptance evidence with model confidence.

---

## Local Control Center

The browser UI remains a projection of the Orqalis core and event model.

Do not create orchestration logic inside React.

---

# 3. Do not depend on GitHub CLI

`git` works in this environment.

`gh` may not.

Therefore GitHub research must NOT depend on GitHub CLI.

Allowed research approaches include:

- web search
- GitHub public pages
- GitHub raw files
- normal `git`
- `git ls-remote`
- shallow temporary clones
- public HTTP APIs when available

Do not classify unavailable `gh` as a project blocker.

---

# 4. Open-source research rule

For every Orqalis subsystem, find multiple serious open-source reference implementations.

Do not choose projects only because they are popular.

Evaluate:

- actual architecture
- implementation quality
- maintenance status
- current activity
- documentation quality
- testing approach
- portability
- local-first compatibility
- extensibility
- security model
- dependency burden
- licensing
- how directly the feature applies to Orqalis

Record the exact repository and inspected revision/date where practical.

---

# 5. Seed reference set

Start with the following projects, but DO NOT limit research to them.

Discover stronger or newer alternatives where appropriate.

## Orchestration / workflows

Study:

- LangGraph
- Microsoft Agent Framework
- CrewAI / Flows
- Temporal concepts where durable execution semantics are useful

Study AutoGen only for useful historical/event-driven ideas because it is no longer the primary forward-looking Microsoft agent framework.

Focus on:

- durable execution
- deterministic + agentic hybrid workflows
- state transitions
- checkpoints
- interruption/resume
- human approval
- retries
- event-driven execution
- task scheduling
- concurrency
- failure handling

Do NOT introduce their database requirements into Orqalis merely to copy their implementation.

Adapt semantics to Orqalis filesystem persistence.

---

# 6. Coding-agent runtime

Study:

- OpenHands
- SWE-agent where useful
- comparable actively maintained coding-agent runtimes

Focus on:

- Action/Observation model
- runtime isolation
- session model
- EventStream patterns
- agent controller boundaries
- execution state
- tool execution
- sandbox interfaces
- process lifecycle
- cancellation
- restart/recovery
- live frontend updates

Determine whether Orqalis has weaker equivalents.

---

# 7. Agent coordination

Study:

- Microsoft Agent Framework
- LangGraph
- CrewAI
- OpenHands
- strong multi-agent research implementations

Compare:

- orchestrator-worker pattern
- supervisor pattern
- parallel workers
- handoffs
- context isolation
- agent mailboxes/messages
- shared blackboard patterns
- event-driven collaboration
- task ownership
- agent termination
- stalled-agent detection

Adapt only patterns that improve deterministic Orqalis control.

Avoid unconstrained agent-to-agent chat.

---

# 8. Skills and agent harness

Study:

- OpenAI Codex skills/plugin behavior
- Anthropic Claude Code skills/plugins/hooks
- GitHub Awesome Copilot agents and skills
- obra/superpowers
- other high-quality skill repositories

Compare:

- SKILL.md discovery
- trigger quality
- progressive disclosure
- metadata-only discovery
- skill references
- bundled scripts
- skill dependencies
- agent-specific vs provider-neutral skills
- automatic selection
- explicit selection
- testing skills
- skill versioning
- skill compatibility
- hooks
- lifecycle events
- subagent invocation

Orqalis must retain its own provider-neutral Skill Registry.

Do not simply install every upstream skill into every project.

---

# 9. Progressive skill loading

Specifically evaluate whether Orqalis can improve context efficiency using a pattern such as:

LEVEL 1
skill metadata

LEVEL 2
SKILL.md only when selected

LEVEL 3
references/examples only when needed

LEVEL 4
scripts/assets only when executed

Measure context reduction.

Do not call this improvement complete without evidence.

---

# 10. Skill quality evaluation

Skills themselves require tests.

Study:

- Superpowers skill testing methodology
- Promptfoo skill evaluation
- Claude plugin validation patterns
- Codex skill selection behavior

Create Orqalis skill evaluations for:

- correct routing
- false-positive routing
- false-negative routing
- instruction adherence
- task quality
- latency
- context cost
- token use where available
- provider portability

A skill that exists but routes poorly is not complete.

---

# 11. Project Memory

Study:

- Serena
- coding-agent-memory-mcp
- Agent-Memory
- Letta concepts where applicable
- official MCP Memory reference implementation
- other strong repo-local coding-memory systems

Compare:

- project onboarding
- memory categories
- Markdown/YAML formats
- progressive references
- memory graph/navigation
- memory freshness
- branch awareness
- memory proposals
- reviewable updates
- search
- tagging
- full-text indexes
- secret scanning
- memory integrity checking
- cross-assistant access
- read-only memories
- memory lifecycle
- forgetting/supersession

Preserve Orqalis's repo-local `.orqalis/memory` architecture.

Do not replace it with a required remote memory service.

---

# 12. Memory progressive discovery

Investigate Serena-style memory references.

Consider an Orqalis-native pattern conceptually similar to:

`mem:architecture`
`mem:frontend/core`
`mem:data/sync`

Do not copy naming blindly.

Evaluate whether explicit memory references improve:

- retrieval precision
- context efficiency
- explainability
- human editability

If adopted, add integrity checking for broken references.

---

# 13. Memory retrieval benchmark

Build representative tasks and measure:

BEFORE:
full/less-selective project context

AFTER:
Orqalis project memory + graph + task history

Record:

- files read
- memories read
- context size
- token usage where measurable
- retrieval relevance
- task success
- time to useful context

Project Memory must prove that it reduces repeated repository rediscovery.

---

# 14. Repository intelligence / graph

Study:

- Graphify
- Aider repo map
- Serena symbolic retrieval
- other strong code graph projects

Compare:

- Tree-sitter/AST extraction
- LSP symbol intelligence
- code symbols
- docs/config/schema ingestion
- call relationships
- import relationships
- inheritance
- cross-language relations
- incremental parsing
- content-hash caches
- branch changes
- dirty working tree changes
- ranking
- communities
- shortest-path queries
- neighborhood traversal
- provenance

---

# 15. Graph provenance

Evaluate Graphify's distinction between deterministic and inferred relations.

Orqalis should clearly distinguish concepts equivalent to:

EXTRACTED
INFERRED

Users and agents must know whether a relationship came directly from source or was inferred.

Add evidence/provenance where missing.

---

# 16. Repository context ranking

Study Aider's repo-map/ranking concepts.

Orqalis should not push the entire graph into every agent context.

Benchmark relevance ranking using signals such as:

- query relevance
- symbol relevance
- graph centrality
- path relevance
- dependency distance
- changed files
- related task history
- memory relationships

Measure whether agents receive smaller but higher-quality Context Packs.

---

# 17. Symbol-aware tools

Study Serena's high-level symbolic code tooling.

Compare Orqalis's current source tools with operations conceptually equivalent to:

- find symbol
- find references
- get symbol body
- replace symbol
- inspect module structure
- identify callers
- identify implementations

Determine whether Orqalis currently relies too heavily on:

- grep
- raw line ranges
- full-file reads

If higher-level symbolic access improves reliability, implement it behind an Orqalis abstraction.

Be careful with licensing.

Do not copy incompatible Serena application code.

---

# 18. Assistant integrations

Benchmark integrations with:

- Codex
- Claude Code
- GitHub Copilot
- MCP-compatible assistants
- OpenCode / Goose / Cursor where useful

Evaluate:

- MCP configuration
- initialization
- root resolution
- tool discovery
- skill discovery
- agent discovery
- hooks
- session start
- session end
- interruption
- context retrieval
- task continuation
- error handling

Orqalis must expose one consistent project intelligence model across assistants.

---

# 19. MCP quality

Study official MCP reference implementations and leading coding-agent MCP servers.

Audit Orqalis for:

- tool naming
- tool count
- schemas
- resource design
- prompts
- errors
- pagination
- root isolation
- transports
- cancellation
- capability negotiation
- reconnect
- long-running calls
- security

Do not expose every internal service as a low-level MCP tool.

Prefer high-value task-oriented interfaces.

---

# 20. Hooks

Study Claude Code and other mature coding assistants.

Evaluate lifecycle hooks around:

- SessionStart
- UserPrompt
- BeforeTool
- AfterTool
- AgentStart
- AgentStop
- BeforeCommit
- ReviewComplete
- TaskComplete
- SessionEnd

Design provider-neutral Orqalis hook semantics where useful.

Possible uses:

- policy
- telemetry
- validation
- context injection
- security
- skill loading
- memory maintenance

Hooks must not create hidden uncontrolled orchestration paths.

---

# 21. Tool permissions

Study permission systems such as those found in mature coding assistants.

Orqalis should support clear tool policy states conceptually similar to:

ALLOW
ASK
DENY

and role-specific permissions.

Examples:

Planner:
read only

Reviewer:
read + tests

Developer:
read/write + allowed execution

Git Delivery:
Git mutation only after gates

Evaluate command-pattern restrictions.

---

# 22. Sandbox / execution isolation

Study:

- OpenHands runtime/sandbox
- Daytona
- other actively maintained sandbox implementations

Benchmark:

- process isolation
- workspace isolation
- resource limits
- timeout
- cancellation
- network policy
- environment variables
- filesystem scope
- snapshots
- cleanup
- parallel sandboxes

Orqalis's standard installation must remain simple.

Do not make Docker or cloud sandboxes mandatory.

Provide adapters/capability tiers if advanced isolation is optional.

---

# 23. Git worktree isolation

Evaluate whether parallel agents should use separate Git worktrees.

Study established coding-agent workflows.

Compare with current Orqalis execution.

Potential target:

task/workstream
â†’ isolated worktree
â†’ agent
â†’ validated change
â†’ controlled integration

Avoid merge chaos.

Add worktree lifecycle cleanup.

---

# 24. Acceptance/review methodology

Study mature coding-agent workflows such as Superpowers and SWE-agent patterns.

Evaluate:

- specification compliance review
- code quality review
- two-stage review
- test-first behavior
- independent reviewer
- evidence requirements
- anti-rationalization guards

Improve Orqalis's acceptance loop where objectively useful.

Do not let implementation agents approve their own final work.

---

# 25. Change Guardian

Benchmark against:

- PR review agents
- static code review tools
- coding-agent review methodologies

Improve detection of:

- scope creep
- unrelated changes
- dependency churn
- config changes
- generated junk
- architecture regression
- security-sensitive files
- accidental large diffs

Add deterministic checks before model review where possible.

---

# 26. Durable execution

Study:

- LangGraph checkpoints
- Temporal workflow semantics
- Microsoft Agent Framework
- other durable execution systems

Orqalis already persists tasks to filesystem.

Improve filesystem semantics rather than introducing a server dependency.

Evaluate:

- checkpoint boundaries
- atomic snapshots
- resumability
- idempotency
- activity retry
- compensation
- timeout
- stuck workflow detection
- deterministic replay where practical

---

# 27. Crash recovery

Create destructive/restart tests:

kill Orqalis during:

- planning
- agent execution
- tool execution
- review
- repair
- documentation
- Git preparation

Restart.

Verify:

- task state is understandable
- completed work is not unnecessarily repeated
- unsafe tool actions are not duplicated
- corrupted snapshots are detected
- recovery path is explicit

---

# 28. Event model

Study OpenHands EventStream and event-driven systems.

Review Orqalis event taxonomy.

Ensure important events are:

- typed
- timestamped
- task-scoped
- actor-scoped
- phase-scoped
- appendable
- serializable
- observable by UI
- safe to persist

Avoid arbitrary log lines as authoritative state.

---

# 29. Control Center

Study:

- OpenHands UI
- agent observability systems
- Langfuse trace UI
- workflow/task monitoring tools

Do NOT clone their visual designs.

Adapt interaction patterns that improve Orqalis.

Review:

- Mission Control
- task graph
- orchestrator
- active agents
- agent task
- phase
- elapsed time
- wait time
- block time
- critical path
- acceptance state
- repair loops
- event stream
- tool actions
- Git state
- Project Brain
- historical runs

---

# 30. Trace hierarchy

Consider a trace structure such as:

Run
â†’ Phase
â†’ Task
â†’ Agent Session
â†’ Model Call
â†’ Tool Call

Compare with current Orqalis.

Ensure UI and diagnostics can correlate these levels.

Do not store private hidden chain-of-thought.

Store:

- structured decisions
- actions
- outcomes
- evidence
- timing
- usage metadata

---

# 31. Timeline

Improve the current timeline/Gantt experience.

It should communicate:

- parallel work
- active work
- waiting
- blocking
- repair cycles
- handoffs
- critical path

Validate on actual multi-agent runs rather than static demo data.

---

# 32. Observability

Study Langfuse and OpenTelemetry-compatible patterns.

Orqalis must remain useful without Langfuse.

Create an internal trace/event abstraction that may optionally export to:

- OpenTelemetry
- Langfuse
- other sinks

Local project telemetry remains the default.

No hosted observability dependency.

---

# 33. Evaluation framework

Study Promptfoo and other coding-agent evaluation systems.

Create a proper Orqalis evaluation suite.

Evaluate:

- orchestrator
- planning
- skill routing
- memory retrieval
- graph retrieval
- coding agent execution
- acceptance review
- repair
- provider adapters
- MCP
- Control Center backend contracts

Use deterministic assertions whenever possible.

Use model judges only where deterministic validation cannot measure quality.

---

# 34. Benchmark dataset

Create a stable local benchmark set containing representative engineering tasks.

Cover:

- small bug fix
- cross-module refactor
- frontend change
- backend change
- architecture change
- test failure
- Git conflict
- documentation-only task
- project-memory lookup
- unfamiliar module
- multi-agent task
- repair-loop task
- security-sensitive change
- interrupted/resumed task

Do not optimize Orqalis to one benchmark only.

---

# 35. Baseline before changing anything

Before implementing enhancement work, capture current metrics.

At minimum where measurable:

- task success
- acceptance first-pass rate
- repair-loop count
- files read
- context bytes/tokens
- model requests
- tool calls
- elapsed time
- active agent time
- waiting time
- graph indexing time
- memory retrieval time
- CLI startup time
- MCP startup time
- UI event latency

Without a baseline you cannot prove improvement.

---

# 36. Open-source comparison matrix

Create:

`docs/quality/OSS_BENCHMARK_MATRIX.md`

For every subsystem include columns conceptually equivalent to:

| Subsystem | Orqalis Current | Reference | Reference Strength | Gap | Proposed Adaptation | Value | Complexity | License Risk | Decision | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|

Do not write vague claims like:

"OpenHands is better."

Identify exact capabilities.

---

# 37. Capability catalog

Create:

`docs/quality/OSS_CAPABILITY_CATALOG.md`

Organize capabilities by subsystem.

For each capability record:

- description
- reference project
- observed implementation pattern
- relevance to Orqalis
- dependency implications
- license
- risk
- whether Orqalis already has it
- whether Orqalis should adopt it

---

# 38. License audit

Create:

`docs/quality/OSS_LICENSE_AUDIT.md`

For each reference project record:

- repository
- component inspected
- license
- whether code reuse is permitted
- attribution requirements
- whether only conceptual adaptation is allowed
- any ambiguity

Important:

Do not copy code solely because it is public on GitHub.

For copyleft or unclear sources, prefer clean-room conceptual adaptation unless explicitly approved.

---

# 39. Decision categories

Every identified capability must end in exactly one of:

KEEP
ADAPT
ADD
REJECT
DEFER

Definitions:

KEEP
Orqalis already has an equal or better implementation.

ADAPT
Orqalis has it, but another design offers measurable improvement.

ADD
High-value missing capability.

REJECT
Not compatible, not valuable, duplicative, too heavy, unsafe, or against Orqalis principles.

DEFER
Useful but not appropriate for the current enhancement cycle.

Never leave important discoveries unclassified.

---

# 40. Selection criteria

Do not implement a feature merely because another project has it.

Evaluate:

- user value
- agent reliability
- context efficiency
- performance
- debuggability
- portability
- local-first compatibility
- provider neutrality
- maintenance burden
- dependency weight
- security
- complexity
- testability
- licensing

Favor simpler Orqalis-native implementations over unnecessary dependencies.

---

# 41. Enhancement backlog

Create:

`docs/quality/ENHANCEMENT_BACKLOG.md`

Each accepted item must have:

- ID
- subsystem
- source/reference inspiration
- current gap
- desired behavior
- acceptance criteria
- test strategy
- benchmark strategy
- estimated impact
- dependencies
- status

---

# 42. Prioritize by dependency, not excitement

Implementation order should normally favor foundations first.

Recommended order:

1. correctness/invariants
2. persistence/recovery
3. context/memory/graph quality
4. skill/agent harness
5. provider/MCP integrations
6. security/permissions
7. execution isolation
8. evaluation
9. observability
10. Control Center UX
11. optimizations

Change order when evidence justifies it.

---

# 43. Implement in small slices

Do not perform one massive merge.

For each enhancement:

READ
â†’ DESIGN
â†’ TEST PLAN
â†’ IMPLEMENT
â†’ TARGETED TEST
â†’ EVAL
â†’ REGRESSION
â†’ DOCUMENT

Only then mark it complete.

---

# 44. Preserve public compatibility

Do not gratuitously break:

- CLI
- `.orqalis` schema
- task history
- MCP APIs
- config
- skills
- plugins
- provider interfaces

If migration is justified:

- version schema
- provide migration
- test it
- document it

---

# 45. Dependency discipline

Before adding any dependency answer:

Can we implement this cleanly ourselves?

Is the dependency actively maintained?

What is its license?

How large is it?

Does it require infrastructure?

Does it conflict with local-first operation?

Would Orqalis become tightly coupled to it?

Prefer adapters over architectural lock-in.

---

# 46. Performance budget

Enhancement work must not make Orqalis unnecessarily heavy.

Track:

- startup
- memory
- disk
- graph index size
- `.orqalis` size
- UI bundle size
- runtime processes
- number of model calls

Reject improvements whose overhead is disproportionate to value.

---

# 47. Low-resource operation

Test on constrained development hardware.

Orqalis should degrade gracefully.

Do not assume:

- massive RAM
- discrete GPU
- Docker
- always-online operation

Optional advanced features must remain optional.

---

# 48. Security review per iteration

After each enhancement wave test:

- path traversal
- command injection
- shell escaping
- task root escape
- project leakage
- secret persistence
- unsafe hooks
- MCP permissions
- arbitrary network access
- unsafe Git operations
- malicious project instructions
- prompt injection from repository content

Treat repository content as untrusted input where appropriate.

---

# 49. Documentation synchronization

After every accepted enhancement update applicable:

- README
- architecture
- implementation status
- agent docs
- skill docs
- memory docs
- MCP docs
- CLI docs
- Control Center docs
- schema docs
- release notes

Remove stale descriptions.

Do not accumulate multiple contradictory architectures.

---

# 50. Repository cleanup after each wave

Search for:

- superseded implementation
- dead adapters
- duplicate models
- stale tests
- outdated docs
- removed dependencies
- experimental files
- obsolete feature flags

Clean them only after proving they are unused.

---

# 51. Continuous comparison loop

At the end of every implementation wave, DO NOT stop.

Run this exact logical loop again:

## LOOP START

### A. Refresh sources

Check whether:

- reference projects changed
- new stronger projects exist
- previous references became stale/unmaintained

---

### B. Re-audit Orqalis

Inspect the actual updated implementation.

---

### C. Rebuild comparison matrix

Update every subsystem's gap state.

---

### D. Re-evaluate DEFER items

Some deferred items may now have become cheap because foundations exist.

---

### E. Run benchmark suite

Compare updated metrics to baseline and previous iteration.

---

### F. Find remaining gaps

Classify all remaining meaningful gaps.

---

### G. Select next wave

Choose the highest-value remaining accepted gaps.

---

### H. Implement

Complete them.

---

### I. Verify

Run targeted and full regression checks.

---

### J. Repeat LOOP START

Do not require the user to repost this prompt for each iteration.

---

# 52. Completion definition

"Everything achieved" does NOT mean copying every feature from every GitHub project.

Completion means all of the following are true.

## Research completeness

Every major Orqalis subsystem has been benchmarked against multiple credible current references.

---

## Decision completeness

Every meaningful discovered capability is classified:

KEEP / ADAPT / ADD / REJECT / DEFER.

---

## High-value gap closure

No accepted P0 or P1 enhancement remains incomplete.

---

## Orchestration

No important identified orchestration reliability gap remains.

---

## Project Memory

Memory benchmark demonstrates useful durable context and avoids unnecessary repeated repo analysis.

---

## Repository Graph

Incremental graph/context retrieval is accurate, provenance-aware and efficient.

---

## Agent/Skill Harness

Skill routing and progressive disclosure perform reliably across representative tests.

---

## Integrations

Codex, Claude/MCP and generic MCP pathways meet the supported integration contract.

---

## Execution

Agents can execute, coordinate, fail, recover and resume safely.

---

## Acceptance

Review and repair loops reliably converge or explicitly block.

---

## Security

No unresolved critical/high findings.

---

## Control Center

UI accurately represents real Orqalis state with no demo/fabricated metrics.

---

## Observability

Important runs/tasks/agents/model/tool actions are traceable.

---

## Evaluation

A repeatable benchmark/eval suite exists and passes.

---

## Regression

Existing Orqalis functionality still passes.

---

## Performance

No unacceptable regression in:

- startup
- memory
- task execution
- project indexing
- context size

---

## Documentation

Canonical documentation describes the actual system.

---

# 53. Quality convergence requirement

Require at least TWO consecutive full benchmark/audit iterations with:

- no newly discovered P0 gaps
- no newly discovered P1 gaps
- no regression
- no broken accepted feature
- no unexplained benchmark degradation

This prevents declaring completion immediately after one improvement pass.

### Release-specific amendment: 2.1.0, 2026-10-09

The user explicitly accepted the measured cold graph-rebuild tradeoff for2.1.0
and deferred its optimization to the next release. [Authorization and scope](evidence/release-cold-performance-user-acceptance-2.1.0-v1.json)
bind this exception to source01d458 and394-inputa0fb. The original investigation
rule and every failed/raw capture remain unchanged. The cause is still unknown;
this is an accepted cost, not a performance fix or a universally clean convergence.
Independent reviewers may accept the two existing exact-source qualifications with
this stated exception. No new correctness/security regression or unrelated timing
failure is waived. Hosted platform and publication gates remain separate.
[Backlog](ENHANCEMENT_BACKLOG.md) owns PERF-COLD-01 for the next release.


---

# 54. Completion sign-off

Create:

`docs/quality/OSS_ENHANCEMENT_SIGNOFF.md`

It must include:

- benchmarked projects
- capabilities evaluated
- features adopted
- features adapted
- rejected/deferred features and reasons
- licenses reviewed
- performance comparison
- eval results
- security result
- regression result
- remaining low-priority opportunities
- final architecture status

Only after this exists may the loop finish.

---

# 55. Progress file

Maintain continuously:

`docs/quality/ENHANCEMENT_STATUS.md`

Include:

- iteration number
- research completed
- current benchmark results
- gaps discovered
- enhancements implemented
- tests
- regressions
- next wave
- current convergence status

This file allows another Codex session to resume the loop correctly.

---

# 56. Context/session limit handling

If the current Codex session reaches context or execution limits:

DO NOT claim completion.

Before ending:

1. finish or safely roll back the current atomic change,
2. run targeted tests,
3. update `ENHANCEMENT_STATUS.md`,
4. update `OSS_BENCHMARK_MATRIX.md`,
5. update `ENHANCEMENT_BACKLOG.md`,
6. record exact next step.

Then output this continuation instruction:

"Continue the Orqalis open-source enhancement loop from `docs/quality/ENHANCEMENT_STATUS.md`. Re-read the benchmark matrix, backlog, adoption decisions and canonical architecture. Resume at the first incomplete accepted enhancement. After completing the current wave, rerun the full research/benchmark/gap loop. Do not stop until the convergence criteria in the master enhancement plan are satisfied."

---

# 57. Do not chase novelty

A newer or more complex implementation is not automatically better.

If Orqalis already provides:

- simpler architecture
- better portability
- lower configuration
- stronger local-first behavior
- clearer evidence
- better project isolation

record:

KEEP

and move on.

---

# 58. No architecture collage

The final Orqalis architecture must not look like:

LangGraph + CrewAI + OpenHands + Serena + Graphify + Langfuse + Temporal + Promptfoo all running simultaneously.

Instead:

Study each.
Extract proven ideas.
Implement coherent Orqalis-native abstractions.
Use external dependencies only where they clearly provide more value than maintenance burden.

Orqalis remains one product.

---

# 59. Attribution

Where a design is materially inspired by another project, record that in the research/architecture documentation.

Where source code is legitimately reused:

- verify license
- preserve required notices
- record provenance

Never conceal copied open-source code.

---

# 60. Initial work partition

Use parallel research subagents where supported.

Suggested independent research streams:

- orchestration/durable execution
- coding-agent runtime/sandbox
- project memory
- repository graph/context
- skills/hooks/agent harness
- MCP/provider integrations
- Control Center/observability
- evaluation/QA/security

Each researcher must return structured evidence, not only opinions.

Then a synthesis agent should deduplicate and reconcile findings.

---

# 61. Research output contract

Each research subagent must report:

PROJECT
SUBSYSTEM
FEATURE
HOW IT WORKS
WHY IT IS EFFECTIVE
ORQALIS CURRENT STATE
GAP
ADAPTATION IDEA
EXPECTED BENEFIT
IMPLEMENTATION COST
LICENSE
RISKS
RECOMMENDATION
EVIDENCE

Do not accept "we should adopt X" without this detail.

---

# 62. Implementation ownership

After synthesis:

Orchestrator
â†’ creates enhancement wave

Planner
â†’ builds DAG

Specialist agents
â†’ implement independent areas in parallel where safe

Reviewer
â†’ specification review

Quality Reviewer
â†’ implementation review

Benchmark Agent
â†’ before/after comparison

Change Guardian
â†’ scope/regression check

Documentation Agent
â†’ synchronize docs

Then restart the research loop.

---

# 63. Do not mutate the existing 2.0.0 release tag

Treat existing release history as immutable.

All enhancement work belongs to current development after the released/tagged baseline.

Do not:

- move `v2.0.0`
- rewrite release history
- amend historical commits

Use normal future development/versioning.

---

# 64. First iteration

Begin now.

Do the following immediately:

1. Inspect the existing Orqalis implementation end to end.
2. Capture the current architecture and quality baseline.
3. Create the quality/research documents listed above.
4. Launch parallel research across the major subsystem categories.
5. Research the seed repositories plus stronger/current alternatives.
6. Verify maintenance state and licensing.
7. Build the first complete capability matrix.
8. Identify what Orqalis already does better.
9. Identify genuine gaps.
10. Classify each gap KEEP/ADAPT/ADD/REJECT/DEFER.
11. Select the first enhancement wave.
12. Write acceptance criteria.
13. Implement the wave.
14. Run targeted tests.
15. Run benchmarks/evals.
16. Run regression tests.
17. Update documentation.
18. Clean stale/superseded code.
19. Re-run the benchmark matrix.
20. Start the next iteration automatically.

Do not stop after research.

Do not stop after generating a plan.

Do not stop after the first implementation wave.

Continue until the convergence/sign-off criteria are satisfied.

---

# FINAL REQUIRED RESULT

When genuinely complete, report:

ORQALIS OPEN-SOURCE BENCHMARK & ENHANCEMENT
============================================

Iterations:
References evaluated:
Capabilities evaluated:

KEEP:
ADAPT:
ADD:
REJECT:
DEFER:

Implemented enhancements:

Orchestration:
PASS

Project Memory:
PASS

Repository Graph:
PASS

Agent Harness:
PASS

Skills:
PASS

Provider Integrations:
PASS

MCP:
PASS

Sandbox / Execution:
PASS

Acceptance / Repair:
PASS

Security:
PASS

Observability:
PASS

Control Center:
PASS

Evaluation:
PASS

Performance:
PASS

Regression:
PASS

Documentation:
PASS

Consecutive clean benchmark iterations:
2 / 2

Remaining:
Only explicitly documented low-value/deferred opportunities.

FINAL STATUS:

CONVERGED