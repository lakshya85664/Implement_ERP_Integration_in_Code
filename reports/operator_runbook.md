# Task 5 — ERP Integration Operator Runbook and Evidence Report

Generated: 2026-11-20T07:38:49.381324+00:00

## 1. Project overview

This project implements a simulated ERP integration for paid source orders.
The workflow validates an order, maps it to an ERP invoice, creates the
invoice and synchronizes inventory. It includes retry handling, replay
protection, reconciliation, adapter boundaries and observability.

The implementation uses a FakeERPSystem/FakeERPAdapter. No live ERP
service is connected.

## 2. Execution commands

Run these commands from the project root with the virtual environment active:

```cmd
python erp_integration.py
python -m py_compile erp_integration.py
python -m pytest tests\\test_task1_contract.py -v
python -m pytest tests\\test_task2_erp_integration.py -v
python -m pytest tests\\test_task3_recovery.py -v
python -m pytest tests\\test_task4_observability.py -v
python -m pytest -q
```

Evidence generation commands:

```cmd
python -c "import json; from erp_integration import run_task3_fixture; print(json.dumps(run_task3_fixture(), indent=2))" > outputs\\task3_erp_recovery.json

python -c "import json; from erp_integration import run_task4_fixture; print(json.dumps(run_task4_fixture(), indent=2))" > outputs\\task4_erp_observability.json

python generate_task5_evidence.py
```

## 3. Workflow outcomes and operator actions

| Scenario | Observed result | Operator action |
|---|---|---|
| Normal success | Order completed; invoice and inventory update created | Verify invoice and inventory references |
| Timeout before commit | First attempt timed out; second attempt completed | Allow bounded retry; verify final state |
| Malformed ERP response | `needs_review`; no automatic retry | Inspect response structure and ERP logs |
| Permanent failure | `needs_review`; operator review required | Correct underlying data/configuration before controlled retry |
| Timeout after commit | Commit reconciled; workflow completed | Verify existing ERP invoice before retrying |
| Duplicate trigger | Replay detected; attempts = 0 | No duplicate action required; verify original result |
| Task 4 invoice timeout | Run failed and trace recorded | Inspect ERP status before deciding whether to retry |

## 4. Output evidence excerpts

### Successful recovery

- Order: `ORDER-RECOVERY-001`
- Status: `completed`
- Invoice: `ERP-INV-ORDER-RECOVERY-001`
- Attempts: 1

### Retry after timeout

- Order: `ORDER-RECOVERY-002`
- First attempt: timeout before commit
- Second attempt: successful
- Attempts: 2

### Reconciliation after commit

- Order: `ORDER-RECOVERY-005`
- Result: `ERP commit confirmed after timeout.`
- Reconciled: true
- Duplicate invoice creation avoided in the fixture.

### Replay protection

- Order: `ORDER-REPLAY-001`
- First run: completed
- Second run: `replayed = true`
- Invoice count: 1
- Inventory update count: 1

### Task 4 failure example

- Order: `ORDER-OBS-002`
- Status: `failed`
- Error type: `ERPTimeoutError`
- Next action: `operator_review`

## 5. Observability metrics

| Metric | Observed value |
|---|---:|
| Runs | 2 |
| Successes | 1 |
| Failures | 1 |
| Adapter operations | 3 |
| Invoices created | 1 |
| Inventory updates | 1 |
| Success rate | 50% |
| Failure rate | 50% |

These metrics are from the Task 4 fixture, which deliberately runs one
successful scenario and one invoice-timeout scenario. They are not
production service-level measurements.

## 6. Trace evidence

Individual scenario traces are exported under `traces/`:

- `success.json`
- `timeout_before_commit.json`
- `malformed_response.json`
- `permanent_failure.json`
- `timeout_after_commit.json`
- `replay_first_run.json`
- `replay_second_run.json`
- `task4_observability.json`

The original full scenario evidence remains in `outputs/`.

## 7. Known limitations

1. The ERP adapter is simulated; no real ERP API or credentials are used.
2. State and replay protection are in memory and are not durable across restarts.
3. Multiple distributed workers are not tested.
4. Invoice creation followed by inventory failure can leave partial state.
5. Production authentication, rate limiting, durable queues, alerting and
   persistent reconciliation are outside this implementation.
6. The metrics represent a small deterministic fixture, not production load.

## 8. Engineering reflection

Building this ERP integration helped me understand that a reliable workflow
requires more than successfully calling an external system. The integration
must also handle uncertainty, duplicate events, partial completion and
operational visibility.

The workflow begins by validating a paid source order and mapping its data
into an ERP invoice. It then creates the invoice and synchronizes inventory.
Separating the ERP adapter from the workflow makes the integration easier to
test and allows a fake adapter to simulate external-system behavior without
depending on a live ERP account.

The recovery tests demonstrated why different failures need different
responses. A timeout before commit was safely retried and completed on the
second attempt. A timeout after commit required reconciliation because the
ERP may have completed the operation even though the response was lost.
The replay test showed that processing the same order again did not create
another invoice or inventory update in the test environment. Malformed
responses and permanent failures were moved to operator review rather than
being retried automatically.

Observability was another important lesson. Structured trace events make it
possible to follow an order through invoice creation and inventory
synchronization. Metrics summarize runs, successes, failures and adapter
operations, while recursive redaction prevents sensitive credential values
from appearing in diagnostic output.

The implementation also has limitations. The ERP is simulated in memory,
so it does not prove behavior against a real ERP API, database or network.
Replay protection is not durable across process restarts or multiple workers.
The workflow can also create an invoice before inventory synchronization
fails, leaving partial state that needs reconciliation. Production use would
require persistent idempotency keys, durable event storage, authentication,
timeouts, rate limiting, stronger transaction or outbox patterns, and
operator alerts with controlled recovery procedures.

Overall, this project improved my understanding of integration boundaries,
failure classification, replay safety and evidence-driven operations. It
also showed why successful execution, recovery behavior and observability
must be tested together before an automation is considered production-ready.

**Reflection word count:** 322
