
"""
Topic 16 — Implement ERP Integration in Code

Tasks included:
1. Workflow Contract and State Model
2. ERP Integration Implementation
3. Failure, Retry, and Replay Safety

Uses a local FakeERPSystem. No production ERP connection.
"""

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ============================================================
# TASK 1 — WORKFLOW CONTRACT AND STATE MODEL
# ============================================================

class WorkflowState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING = "waiting"
    COMPLETED = "completed"
    NEEDS_REVIEW = "needs_review"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class EventType(str, Enum):
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_PAUSED = "workflow.paused"
    WORKFLOW_RESUMED = "workflow.resumed"
    WORKFLOW_FAILED = "workflow.failed"
    TASK_STARTED = "task.started"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class WorkflowInput(BaseModel):
    """Typed input identifying the source business transaction."""

    source_system: str = Field(min_length=1)
    business_key: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class WorkflowTask(BaseModel):
    """A unit of work within the ERP synchronization workflow."""

    model_config = ConfigDict(validate_assignment=True)

    task_id: str
    name: str
    status: TaskStatus = TaskStatus.PENDING
    attempts: int = Field(default=0, ge=0)
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class WorkflowEvent(BaseModel):
    """A structured workflow event."""

    event_id: str
    run_id: str
    event_type: EventType
    state: WorkflowState
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    details: dict[str, Any] = Field(default_factory=dict)


class WorkflowResult(BaseModel):
    """Final or intermediate outcome of a workflow run."""

    status: WorkflowState
    source_order_id: str | None = None
    erp_invoice_id: str | None = None
    inventory_reference: str | None = None
    message: str = ""
    data: dict[str, Any] = Field(default_factory=dict)


class WorkflowRun(BaseModel):
    """Tracks workflow state, tasks, context, and execution history."""

    model_config = ConfigDict(validate_assignment=True)

    run_id: str
    business_key: str
    state: WorkflowState = WorkflowState.CREATED
    attempts: int = Field(default=0, ge=0)
    context: dict[str, Any] = Field(default_factory=dict)
    tasks: list[WorkflowTask] = Field(default_factory=list)
    events: list[WorkflowEvent] = Field(default_factory=list)
    result: WorkflowResult | None = None

    def record(
        self,
        event_type: EventType,
        details: dict[str, Any] | None = None,
    ) -> None:
        event = WorkflowEvent(
            event_id=f"{self.run_id}-EVENT-{len(self.events) + 1:03d}",
            run_id=self.run_id,
            event_type=event_type,
            state=self.state,
            details=details or {},
        )
        self.events.append(event)


LEGAL_TRANSITIONS = {
    (WorkflowState.CREATED, "start"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "complete"): WorkflowState.COMPLETED,
    (WorkflowState.RUNNING, "pause"): WorkflowState.WAITING,
    (WorkflowState.WAITING, "resume"): WorkflowState.RUNNING,
    (WorkflowState.RUNNING, "fail"): WorkflowState.NEEDS_REVIEW,
}


def transition(run: WorkflowRun, event: str) -> WorkflowRun:
    """Apply one legal state transition or reject it."""

    next_state = LEGAL_TRANSITIONS.get((run.state, event))

    if next_state is None:
        raise ValueError(
            f"Illegal workflow transition: {run.state.value} -> {event}"
        )

    run.state = next_state

    event_mapping = {
        "start": EventType.WORKFLOW_STARTED,
        "complete": EventType.WORKFLOW_COMPLETED,
        "pause": EventType.WORKFLOW_PAUSED,
        "resume": EventType.WORKFLOW_RESUMED,
        "fail": EventType.WORKFLOW_FAILED,
    }

    run.record(
        event_mapping[event],
        {
            "transition": event,
            "new_state": next_state.value,
        },
    )

    return run


def run_task1_fixture() -> dict[str, Any]:
    """Demonstrate creation and start of an ERP workflow."""

    workflow_input = WorkflowInput(
        source_system="online_store",
        business_key="ORDER-1001",
        payload={
            "order_id": "ORDER-1001",
            "payment_status": "paid",
        },
    )

    run = WorkflowRun(
        run_id="ERP-RUN-001",
        business_key=workflow_input.business_key,
        context=workflow_input.payload,
        tasks=[
            WorkflowTask(
                task_id="TASK-001",
                name="validate_paid_order",
            ),
            WorkflowTask(
                task_id="TASK-002",
                name="create_erp_invoice",
            ),
            WorkflowTask(
                task_id="TASK-003",
                name="synchronize_inventory",
            ),
        ],
    )

    run.record(
        EventType.WORKFLOW_STARTED,
        {"source_system": workflow_input.source_system},
    )

    transition(run, "start")

    return {
        "input": workflow_input.model_dump(mode="json"),
        "run": run.model_dump(mode="json"),
        "legal_transitions": [
            {
                "from": source.value,
                "event": event,
                "to": target.value,
            }
            for (source, event), target in LEGAL_TRANSITIONS.items()
        ],
    }


# ============================================================
# TASK 2 — ERP INTEGRATION IMPLEMENTATION
# ============================================================

class SourceOrder(BaseModel):
    """Online-store order schema."""

    order_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    customer_name: str = Field(min_length=1)
    customer_email: str = Field(min_length=1)
    payment_status: str
    currency: str = "INR"
    items: list[dict[str, Any]] = Field(min_length=1)


class ERPInvoice(BaseModel):
    """ERP invoice schema."""

    invoice_id: str
    source_order_id: str
    customer_code: str
    customer_name: str
    currency: str
    total_amount: float
    lines: list[dict[str, Any]]


class InventoryUpdate(BaseModel):
    """ERP inventory synchronization result."""

    reference_id: str
    source_order_id: str
    items_updated: int
    quantities: dict[str, int]


class FakeERPSystem:
    """
    Local ERP substitute for the assessment.

    Starting stock is synthetic and exists only for testing.
    """

    def __init__(self):
        self.invoices: dict[str, dict[str, Any]] = {}

        self.inventory: dict[str, int] = {
            "LAPTOP-001": 100,
            "MOUSE-002": 100,
            "SKU-001": 100,
        }

        self.inventory_updates: list[dict[str, Any]] = []

    def create_invoice(
        self,
        invoice: ERPInvoice,
    ) -> dict[str, Any]:
        if invoice.invoice_id in self.invoices:
            raise ValueError("Invoice already exists")

        data = invoice.model_dump(mode="json")
        self.invoices[invoice.invoice_id] = data

        return data

    def update_inventory(
        self,
        source_order_id: str,
        quantities: dict[str, int],
    ) -> dict[str, Any]:
        """Validate all stock before applying inventory changes."""

        for sku, quantity in quantities.items():
            if sku not in self.inventory:
                raise ValueError(f"Unknown inventory SKU: {sku}")

            if isinstance(quantity, bool) or not isinstance(quantity, int):
                raise ValueError(f"Invalid quantity for {sku}")

            if quantity <= 0:
                raise ValueError(f"Invalid inventory quantity for {sku}")

            if self.inventory[sku] < quantity:
                raise ValueError(f"Insufficient stock for {sku}")

        # Apply only after all items pass validation.
        for sku, quantity in quantities.items():
            self.inventory[sku] -= quantity

        reference = f"INV-STOCK-{len(self.inventory_updates) + 1:04d}"

        result = {
            "reference_id": reference,
            "source_order_id": source_order_id,
            "items_updated": len(quantities),
            "quantities": quantities,
        }

        self.inventory_updates.append(result)

        return result


def map_order_to_invoice(
    order: SourceOrder,
    invoice_id: str,
) -> ERPInvoice:
    """Map online-store order fields to ERP invoice fields."""

    lines = []
    total = Decimal("0")

    for item in order.items:
        sku = str(item.get("sku", "")).strip()

        if not sku:
            raise ValueError("Item SKU is required")

        quantity = item.get("quantity")

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError(f"Invalid quantity for SKU {sku}")

        if quantity <= 0:
            raise ValueError(f"Quantity must be positive for SKU {sku}")

        try:
            price = Decimal(str(item.get("unit_price")))
        except (InvalidOperation, TypeError, ValueError):
            raise ValueError(f"Invalid unit price for SKU {sku}")

        if not price.is_finite() or price < 0:
            raise ValueError(
                f"Unit price must be non-negative for SKU {sku}"
            )

        line_total = price * quantity
        total += line_total

        lines.append({
            "item_code": sku,
            "description": str(item.get("name", sku)),
            "quantity": quantity,
            "unit_price": float(price),
            "line_total": float(line_total),
        })

    return ERPInvoice(
        invoice_id=invoice_id,
        source_order_id=order.order_id,
        customer_code=order.customer_id,
        customer_name=order.customer_name,
        currency=order.currency,
        total_amount=float(total),
        lines=lines,
    )


def get_inventory_quantities(
    order: SourceOrder,
) -> dict[str, int]:
    """Aggregate quantities when an order contains repeated SKUs."""

    quantities: dict[str, int] = {}

    for item in order.items:
        sku = str(item["sku"]).strip()
        quantity = item["quantity"]

        if isinstance(quantity, bool) or not isinstance(quantity, int):
            raise ValueError(f"Invalid quantity for SKU {sku}")

        quantities[sku] = quantities.get(sku, 0) + quantity

    return quantities


def synchronize_paid_order(
    raw_order: dict[str, Any],
    erp: FakeERPSystem,
) -> dict[str, Any]:
    """
    Validate a paid order, map it to an ERP invoice,
    create the invoice, and synchronize inventory.
    """

    try:
        order = SourceOrder.model_validate(raw_order)

        if order.payment_status.strip().lower() != "paid":
            raise ValueError("Order payment is not completed")

        if not order.currency.strip():
            raise ValueError("Currency is required")

        invoice_id = f"ERP-INV-{order.order_id}"

        invoice = map_order_to_invoice(order, invoice_id)
        inventory_quantities = get_inventory_quantities(order)

        # Check inventory before creating the invoice.
        for sku, quantity in inventory_quantities.items():
            if sku not in erp.inventory:
                raise ValueError(f"Unknown inventory SKU: {sku}")

            if erp.inventory[sku] < quantity:
                raise ValueError(f"Insufficient stock for {sku}")

        created_invoice = erp.create_invoice(invoice)

        inventory_result = erp.update_inventory(
            order.order_id,
            inventory_quantities,
        )

        return {
            "status": "completed",
            "source_order_id": order.order_id,
            "invoice": created_invoice,
            "inventory": inventory_result,
            "message": "Order successfully synchronized with ERP.",
        }

    except Exception as exc:
        return {
            "status": "failed",
            "source_order_id": raw_order.get("order_id"),
            "error_type": type(exc).__name__,
            "error": str(exc),
            "next_action": "review_input_or_integration",
        }


def run_task2_fixture() -> dict[str, Any]:
    """Run a deterministic paid-order ERP integration fixture."""

    erp = FakeERPSystem()

    order = {
        "order_id": "ORDER-2001",
        "customer_id": "CUST-101",
        "customer_name": "Aarav Sharma",
        "customer_email": "aarav@example.com",
        "payment_status": "paid",
        "currency": "INR",
        "items": [
            {
                "sku": "LAPTOP-001",
                "name": "Business Laptop",
                "quantity": 2,
                "unit_price": 45000,
            },
            {
                "sku": "MOUSE-002",
                "name": "Wireless Mouse",
                "quantity": 3,
                "unit_price": 750,
            },
        ],
    }

    result = synchronize_paid_order(order, erp)

    return {
        "result": result,
        "erp_state": {
            "invoices": erp.invoices,
            "inventory": erp.inventory,
            "inventory_updates": erp.inventory_updates,
        },
    }


# ============================================================
# TASK 3 — FAILURE, RETRY, AND REPLAY SAFETY
# ============================================================

class ERPTimeoutError(Exception):
    """Simulated temporary ERP timeout."""


class ERPMalformedResponseError(Exception):
    """Simulated malformed ERP response."""


class ERPPermanentError(Exception):
    """Simulated permanent ERP failure."""


def run_erp_with_recovery(
    raw_order: dict[str, Any],
    erp: FakeERPSystem,
    scenario: str = "success",
    max_retries: int = 2,
) -> dict[str, Any]:
    """
    Execute ERP synchronization with bounded retries,
    duplicate prevention, and timeout reconciliation.

    Supported scenarios:
      success
      timeout_before_commit
      malformed_response
      permanent_failure
      timeout_after_commit
      duplicate_trigger
    """

    if isinstance(max_retries, bool) or not isinstance(max_retries, int):
        raise ValueError("max_retries must be an integer")

    if max_retries < 0:
        raise ValueError("max_retries cannot be negative")

    order_id = str(raw_order.get("order_id", "")).strip()

    if not order_id:
        return {
            "status": "failed",
            "error": "Missing order ID",
            "next_action": "review_input",
            "attempts": 0,
            "trace": [],
        }

    # Local in-memory idempotency store.
    if not hasattr(erp, "processed_orders"):
        erp.processed_orders = {}

    trace = []

    # Prevent a completed order from repeating side effects.
    if order_id in erp.processed_orders:
        trace.append({
            "event": "duplicate_prevented",
            "order_id": order_id,
        })

        return {
            **erp.processed_orders[order_id],
            "replayed": True,
            "attempts": 0,
            "trace": trace,
        }

    if scenario == "duplicate_trigger":
        trace.append({
            "event": "duplicate_prevented",
            "order_id": order_id,
        })

        return {
            "status": "duplicate_prevented",
            "order_id": order_id,
            "attempts": 0,
            "next_action": "use_existing_result",
            "trace": trace,
        }

    if scenario == "malformed_response":
        trace.append({
            "event": "malformed_response",
            "attempt": 1,
            "retryable": False,
        })

        return {
            "status": "needs_review",
            "error_type": "ERPMalformedResponseError",
            "attempts": 1,
            "next_action": "inspect_erp_response",
            "trace": trace,
        }

    if scenario == "permanent_failure":
        trace.append({
            "event": "permanent_failure",
            "attempt": 1,
            "retryable": False,
        })

        return {
            "status": "needs_review",
            "error_type": "ERPPermanentError",
            "attempts": 1,
            "next_action": "operator_review",
            "trace": trace,
        }

    if scenario not in {
        "success",
        "timeout_before_commit",
        "timeout_after_commit",
    }:
        return {
            "status": "needs_review",
            "error": f"Unknown scenario: {scenario}",
            "attempts": 0,
            "next_action": "review_scenario",
            "trace": trace,
        }

    attempts = 0
    timeout_before_commit_used = False

    while attempts <= max_retries:
        attempts += 1

        trace.append({
            "event": "attempt_started",
            "attempt": attempts,
            "order_id": order_id,
        })

        try:
            if (
                scenario == "timeout_before_commit"
                and not timeout_before_commit_used
            ):
                timeout_before_commit_used = True

                raise ERPTimeoutError(
                    "ERP request timed out before commit"
                )

            result = synchronize_paid_order(raw_order, erp)

            if result["status"] != "completed":
                trace.append({
                    "event": "integration_failed",
                    "attempt": attempts,
                    "error": result.get("error"),
                })

                return {
                    **result,
                    "attempts": attempts,
                    "next_action": "operator_review",
                    "trace": trace,
                }

            # Simulate a timeout after both ERP side effects commit.
            if scenario == "timeout_after_commit":
                scenario = "success"

                trace.append({
                    "event": "timeout_after_commit",
                    "attempt": attempts,
                    "reconciliation_required": True,
                })

                invoice_id = f"ERP-INV-{order_id}"

                committed_invoice = erp.invoices.get(invoice_id)

                committed_inventory = next(
                    (
                        update
                        for update in erp.inventory_updates
                        if update["source_order_id"] == order_id
                    ),
                    None,
                )

                if committed_invoice and committed_inventory:
                    reconciled = {
                        **result,
                        "status": "completed",
                        "reconciled": True,
                        "message": (
                            "ERP commit confirmed after timeout."
                        ),
                    }

                    erp.processed_orders[order_id] = reconciled

                    trace.append({
                        "event": "commit_reconciled",
                        "invoice_id": invoice_id,
                        "inventory_reference":
                            committed_inventory["reference_id"],
                    })

                    return {
                        **reconciled,
                        "attempts": attempts,
                        "trace": trace,
                    }

                raise ERPTimeoutError(
                    "ERP commit could not be reconciled"
                )

            erp.processed_orders[order_id] = result

            trace.append({
                "event": "integration_completed",
                "attempt": attempts,
                "invoice_id": result["invoice"]["invoice_id"],
            })

            return {
                **result,
                "attempts": attempts,
                "replayed": False,
                "trace": trace,
            }

        except ERPTimeoutError as exc:
            trace.append({
                "event": "timeout",
                "attempt": attempts,
                "error": str(exc),
                "retryable": True,
            })

            if attempts > max_retries:
                return {
                    "status": "needs_review",
                    "error_type": "ERPTimeoutError",
                    "attempts": attempts,
                    "next_action": "manual_reconciliation",
                    "trace": trace,
                }

            trace.append({
                "event": "retry_scheduled",
                "next_attempt": attempts + 1,
            })

    return {
        "status": "needs_review",
        "attempts": attempts,
        "next_action": "operator_review",
        "trace": trace,
    }


def run_task3_fixture() -> dict[str, Any]:
    """Generate deterministic recovery scenario evidence."""

    scenarios = [
        "success",
        "timeout_before_commit",
        "malformed_response",
        "permanent_failure",
        "timeout_after_commit",
    ]

    evidence = {}

    for index, scenario in enumerate(scenarios, start=1):
        erp = FakeERPSystem()

        order = {
            "order_id": f"ORDER-RECOVERY-{index:03d}",
            "customer_id": "CUST-RECOVERY",
            "customer_name": "Recovery Test",
            "customer_email": "recovery@example.com",
            "payment_status": "paid",
            "currency": "INR",
            "items": [
                {
                    "sku": "LAPTOP-001",
                    "name": "Business Laptop",
                    "quantity": 1,
                    "unit_price": 45000,
                }
            ],
        }

        evidence[scenario] = run_erp_with_recovery(
            order,
            erp,
            scenario=scenario,
            max_retries=2,
        )

    # Replay prevention demonstration.
    replay_erp = FakeERPSystem()

    replay_order = {
        "order_id": "ORDER-REPLAY-001",
        "customer_id": "CUST-REPLAY",
        "customer_name": "Replay Test",
        "customer_email": "replay@example.com",
        "payment_status": "paid",
        "currency": "INR",
        "items": [
            {
                "sku": "LAPTOP-001",
                "name": "Business Laptop",
                "quantity": 1,
                "unit_price": 45000,
            }
        ],
    }

    first_run = run_erp_with_recovery(
        replay_order,
        replay_erp,
    )

    second_run = run_erp_with_recovery(
        replay_order,
        replay_erp,
    )

    evidence["replay_test"] = {
        "first_run": first_run,
        "second_run": second_run,
        "invoice_count": len(replay_erp.invoices),
        "inventory_update_count": len(replay_erp.inventory_updates),
    }

    return evidence


# ============================================================
# MAIN EXECUTION
# ============================================================

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("TOPIC 16 — ERP INTEGRATION")
    print("WORKFLOW CONTRACT AND STATE MODEL")
    print("=" * 60)

    print(
        json.dumps(
            run_task1_fixture(),
            indent=2,
        )
    )


# ============================================================
# TASK 4 — INTEGRATION BOUNDARY AND OBSERVABILITY
# ============================================================

from typing import Protocol
import re


class ERPAdapter(Protocol):
    """Contract for interchangeable ERP implementations."""

    def create_invoice(
        self,
        invoice: ERPInvoice,
    ) -> dict[str, Any]:
        ...

    def update_inventory(
        self,
        source_order_id: str,
        quantities: dict[str, int],
    ) -> dict[str, Any]:
        ...


class FakeERPAdapter(FakeERPSystem):
    """Test adapter implementing the ERP interface."""

    def __init__(self, failure_mode: str | None = None):
        super().__init__()
        self.failure_mode = failure_mode
        self.operation_count = 0

    def create_invoice(
        self,
        invoice: ERPInvoice,
    ) -> dict[str, Any]:
        self.operation_count += 1

        if self.failure_mode == "invoice_timeout":
            raise ERPTimeoutError("ERP invoice request timed out")

        if self.failure_mode == "invoice_permanent":
            raise ERPPermanentError("ERP invoice creation rejected")

        return super().create_invoice(invoice)

    def update_inventory(
        self,
        source_order_id: str,
        quantities: dict[str, int],
    ) -> dict[str, Any]:
        self.operation_count += 1

        if self.failure_mode == "inventory_timeout":
            raise ERPTimeoutError("ERP inventory request timed out")

        if self.failure_mode == "inventory_permanent":
            raise ERPPermanentError("ERP inventory update rejected")

        return super().update_inventory(
            source_order_id,
            quantities,
        )


class ERPObservability:
    """Collect structured traces and integration metrics."""

    def __init__(self):
        self.traces: list[dict[str, Any]] = []
        self.metrics = {
            "runs": 0,
            "successes": 0,
            "failures": 0,
            "adapter_operations": 0,
            "invoices_created": 0,
            "inventory_updates": 0,
        }

    def record(
        self,
        event: str,
        order_id: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.traces.append({
            "event": event,
            "order_id": order_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        })

    def get_metrics(self) -> dict[str, Any]:
        runs = self.metrics["runs"]

        return {
            **self.metrics,
            "success_rate": (
                self.metrics["successes"] / runs
                if runs else 0.0
            ),
            "failure_rate": (
                self.metrics["failures"] / runs
                if runs else 0.0
            ),
        }

    def get_trace(self, order_id: str) -> list[dict[str, Any]]:
        return [
            trace
            for trace in self.traces
            if trace["order_id"] == order_id
        ]


def redact_secrets(data: Any) -> Any:
    """Recursively redact values belonging to sensitive fields."""

    sensitive_fields = {
        "password",
        "token",
        "access_token",
        "refresh_token",
        "api_key",
        "authorization",
        "secret",
    }

    if isinstance(data, dict):
        return {
            key: (
                "***REDACTED***"
                if key.lower() in sensitive_fields
                else redact_secrets(value)
            )
            for key, value in data.items()
        }

    if isinstance(data, list):
        return [redact_secrets(item) for item in data]

    if isinstance(data, tuple):
        return tuple(redact_secrets(item) for item in data)

    return data


def run_with_erp_adapter(
    raw_order: dict[str, Any],
    adapter: ERPAdapter,
    observability: ERPObservability,
) -> dict[str, Any]:
    """
    Execute the ERP integration using an injected adapter
    while collecting traces and metrics.
    """

    order_id = str(raw_order.get("order_id", "")).strip()

    observability.metrics["runs"] += 1

    observability.record(
        "integration.started",
        order_id,
    )

    try:
        order = SourceOrder.model_validate(raw_order)

        if order.payment_status.strip().lower() != "paid":
            raise ValueError("Order payment is not completed")

        if not order.currency.strip():
            raise ValueError("Currency is required")

        invoice = map_order_to_invoice(
            order,
            f"ERP-INV-{order.order_id}",
        )

        quantities = get_inventory_quantities(order)

        observability.record(
            "invoice.creation.started",
            order_id,
        )

        created_invoice = adapter.create_invoice(invoice)

        observability.record(
            "invoice.created",
            order_id,
            {"invoice_id": created_invoice["invoice_id"]},
        )

        observability.metrics["invoices_created"] += 1

        observability.record(
            "inventory.synchronization.started",
            order_id,
        )

        inventory_result = adapter.update_inventory(
            order_id,
            quantities,
        )

        observability.record(
            "inventory.synchronized",
            order_id,
            {
                "reference_id": inventory_result["reference_id"],
                "items_updated": inventory_result["items_updated"],
            },
        )

        observability.metrics["inventory_updates"] += 1
        observability.metrics["successes"] += 1

        result = {
            "status": "completed",
            "source_order_id": order_id,
            "invoice": created_invoice,
            "inventory": inventory_result,
        }

        observability.record(
            "integration.completed",
            order_id,
        )

        return result

    except Exception as exc:
        observability.metrics["failures"] += 1

        observability.record(
            "integration.failed",
            order_id,
            {
                "error_type": type(exc).__name__,
                "error": str(exc),
            },
        )

        return {
            "status": "failed",
            "source_order_id": order_id,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "next_action": "operator_review",
        }

    finally:
        observability.metrics["adapter_operations"] += (
            getattr(adapter, "operation_count", 0)
        )


def get_erp_health(adapter: ERPAdapter) -> dict[str, Any]:
    """Return basic health information for the local adapter."""

    return {
        "status": "available",
        "adapter": type(adapter).__name__,
        "invoice_count": len(adapter.invoices),
        "inventory_update_count": len(adapter.inventory_updates),
    }


def run_task4_fixture() -> dict[str, Any]:
    """Generate successful and failed integration observations."""

    observability = ERPObservability()

    order = {
        "order_id": "ORDER-OBS-001",
        "customer_id": "CUST-OBS-001",
        "customer_name": "Observability Test",
        "customer_email": "observe@example.com",
        "payment_status": "paid",
        "currency": "INR",
        "items": [
            {
                "sku": "LAPTOP-001",
                "name": "Business Laptop",
                "quantity": 1,
                "unit_price": 45000,
            }
        ],
    }

    success_adapter = FakeERPAdapter()

    success_result = run_with_erp_adapter(
        order,
        success_adapter,
        observability,
    )

    failed_order = {
        **order,
        "order_id": "ORDER-OBS-002",
    }

    failed_adapter = FakeERPAdapter(
        failure_mode="invoice_timeout"
    )

    failure_result = run_with_erp_adapter(
        failed_order,
        failed_adapter,
        observability,
    )

    sensitive_sample = {
        "customer": "Test Customer",
        "api_key": "sample-secret-key",
        "credentials": {
            "password": "sample-password",
            "access_token": "sample-access-token",
        },
    }

    return {
        "successful_run": success_result,
        "failed_run": failure_result,
        "metrics": observability.get_metrics(),
        "traces": observability.traces,
        "health": get_erp_health(success_adapter),
        "redaction_demo": redact_secrets(sensitive_sample),
    }
