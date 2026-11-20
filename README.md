# Topic 16 — Implement ERP Integration in Code

## Project Overview

This project implements an ERP integration workflow that synchronizes paid customer orders with an ERP system. It demonstrates workflow state management, order-to-invoice mapping, inventory updates, failure recovery, retry handling, replay safety, integration boundaries, and observability.

A simulated ERP system is used to test integration behavior without requiring a real ERP account or external service.

## Objectives

- Define workflow states and valid state transitions.
- Implement order-to-invoice mapping.
- Synchronize paid orders with ERP invoices and inventory.
- Handle timeouts, malformed responses, and permanent failures.
- Implement retry and replay-safe behavior.
- Create an ERP adapter boundary using a Python Protocol.
- Capture operational metrics, health information, and structured evidence.
- Prepare an operator runbook for troubleshooting and recovery.

## Project Structure

```text
Implement_ERP_Integration_in_Code/
│
├── erp_integration.py
├── generate_task5_evidence.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── tests/
│   └── test_erp_integration.py
│
├── outputs/
│   ├── task1_workflow_contract.json
│   ├── task2_erp_integration.json
│   ├── task3_erp_recovery.json
│   └── task4_erp_observability.json
│
├── traces/
│   ├── success.json
│   ├── timeout_before_commit.json
│   ├── malformed_response.json
│   ├── permanent_failure.json
│   ├── timeout_after_commit.json
│   ├── replay_first_run.json
│   ├── replay_second_run.json
│   └── task4_observability.json
│
├── reports/
│   └── operator_runbook.md
│
└── diagrams/
```

## Technology Stack

- Python 3.13.9
- Pydantic 2.14.3
- Pytest 9.2.0
- JSON for structured evidence and traces
- Python Protocol for adapter abstraction

## Installation and Setup

### 1. Create and activate a virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 2. Install dependencies

```cmd
pip install -r requirements.txt
```

## Implementation Tasks

### Task 1 — Workflow Contract and State Model

Defined the workflow contract, order data structures, workflow states, and permitted state transitions.

Evidence:
- `outputs/task1_workflow_contract.json`

### Task 2 — ERP Integration Implementation

Implemented the simulated ERP integration, including:

- Source order validation.
- Mapping source orders to ERP invoices.
- Invoice creation.
- Inventory validation and stock updates.
- Paid-order synchronization.

Evidence:
- `outputs/task2_erp_integration.json`

### Task 3 — Failure, Retry, and Replay Safety

Implemented recovery mechanisms for common integration failures:

- Timeout before commit.
- Malformed ERP responses.
- Permanent failures.
- Timeout after commit.
- Duplicate triggers.
- Replay after successful completion.

The implementation uses retry handling and replay checks to reduce duplicate invoice and inventory operations.

Evidence:
- `outputs/task3_erp_recovery.json`
- Trace files in `traces/`

### Task 4 — Integration Boundary and Observability

Introduced an ERP adapter interface using Python Protocol and implemented a fake adapter for testing.

Additional features:

- Structured operational metrics.
- ERP health checks.
- Secret redaction.
- Success and failure tracking.
- Adapter operation monitoring.

Evidence:
- `outputs/task4_erp_observability.json`
- `traces/task4_observability.json`

### Task 5 — Operator Runbook and Evidence Report

Created an operator runbook documenting:

- Successful integration scenarios.
- Failure and recovery scenarios.
- Replay behavior.
- Commands for running and testing the project.
- Trace files and output evidence.
- Operational metrics.
- Known limitations.
- Engineering reflection.

Evidence:
- `reports/operator_runbook.md`

## Running the Project

Activate the virtual environment:

```cmd
.venv\Scripts\activate
```

Run the test suite:

```cmd
python -m pytest -q
```

Generate Task 5 evidence:

```cmd
python generate_task5_evidence.py
```

Review the operator runbook:

```cmd
type reports\operator_runbook.md
```

## Test Results

All five implementation tasks were completed and verified.

**Final test result: 35 passed**

The test suite validates workflow contracts, ERP synchronization, failure recovery, replay safety, adapter behavior, observability, and evidence generation.

## Operational Metrics

The observability fixture recorded the following results:

| Metric | Result |
|---|---:|
| Total runs | 2 |
| Successful runs | 1 |
| Failed runs | 1 |
| Adapter operations | 3 |
| Invoices created | 1 |
| Inventory updates | 1 |
| Success rate | 50% |
| Failure rate | 50% |

These metrics are based on the Task 4 test fixture and are not production performance measurements.

## Known Limitations

- The ERP system is simulated using a fake adapter.
- Replay protection is maintained in memory and is not durable across application restarts or multiple workers.
- Inventory and invoice operations are not protected by a distributed transaction.
- A timeout during inventory synchronization can leave partial state.
- Production deployment would require persistent idempotency records, reconciliation, secure credential management, and stronger transaction or outbox mechanisms.

## Engineering Reflection

This project helped me understand how ERP integrations work beyond simple API communication. I learned that integrating two business systems requires careful handling of workflow states, data mapping, failures, retries, and operational visibility.

During the implementation, I created a workflow contract to define valid states and transitions. I then implemented order-to-invoice mapping and inventory synchronization using a simulated ERP system. This helped me understand how source-system data can be transformed into ERP-compatible structures.

One of the most important parts of this project was failure recovery. I implemented handling for timeouts, malformed responses, permanent failures, and duplicate triggers. I also explored replay safety and learned why an integration must verify whether an operation has already been completed before executing it again.

The adapter pattern helped separate the business workflow from the ERP implementation. This makes the system easier to test and allows a simulated adapter to be replaced with a real ERP adapter in the future.

I also implemented observability features such as operational metrics, health checks, structured traces, and secret redaction. Preparing the operator runbook improved my understanding of how engineers investigate failures and recover integrations.

Overall, this project strengthened my practical knowledge of Python, Pydantic, testing, workflow orchestration, error handling, and integration design. It also showed me why production integrations need durable idempotency, reconciliation, and reliable transaction handling.

## Conclusion

The project successfully demonstrates a structured ERP integration workflow with state management, invoice creation, inventory synchronization, failure recovery, replay protection, adapter abstraction, observability, and operator documentation.

All 35 automated tests passed, and the required evidence and runbook files were generated.