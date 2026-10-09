# Actual runtime trace fixture

`runtime-trace.json` is a RunSnapshot exported by
`tests/integration/test_trace_projection.py` after executing real project-local
orchestration with an injected deterministic provider. Two architect tasks overlap;
source validation and independent review fail; a repair plan succeeds. The run also
contains an actual pause/resume before execution. Timestamps, durations, identities,
evidence links and parent relationships come from filesystem persistence.

Regenerate from the repository root in PowerShell:

```powershell
$env:ORQALIS_TRACE_SNAPSHOT_FIXTURE = "$PWD/web/src/fixtures/runtime-trace.json"
.venv/Scripts/python.exe -m pytest tests/integration/test_trace_projection.py -q
Remove-Item Env:ORQALIS_TRACE_SNAPSHOT_FIXTURE
```

This fixture qualifies the projection and UI, not a native assistant/model integration
or network telemetry exporter. Raw provider output is not part of the trace hierarchy.
