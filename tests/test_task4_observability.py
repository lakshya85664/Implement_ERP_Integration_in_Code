
import pytest

from erp_integration import (
    FakeERPAdapter,
    ERPObservability,
    run_with_erp_adapter,
    get_erp_health,
    redact_secrets,
    run_task4_fixture,
)


def sample_order(order_id="ORDER-OBS-TEST"):
    return {
        "order_id": order_id,
        "customer_id": "CUST-OBS",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "payment_status": "paid",
        "currency": "INR",
        "items": [
            {
                "sku": "LAPTOP-001",
                "name": "Laptop",
                "quantity": 1,
                "unit_price": 45000,
            }
        ],
    }


def test_successful_adapter_injection():
    adapter = FakeERPAdapter()
    observability = ERPObservability()

    result = run_with_erp_adapter(
        sample_order(),
        adapter,
        observability,
    )

    assert result["status"] == "completed"
    assert len(adapter.invoices) == 1
    assert len(adapter.inventory_updates) == 1


def test_adapter_timeout_is_observed():
    adapter = FakeERPAdapter(failure_mode="invoice_timeout")
    observability = ERPObservability()

    result = run_with_erp_adapter(
        sample_order(),
        adapter,
        observability,
    )

    assert result["status"] == "failed"
    assert result["error_type"] == "ERPTimeoutError"
    assert observability.metrics["failures"] == 1


def test_metrics_count_success_and_failure():
    evidence = run_task4_fixture()

    metrics = evidence["metrics"]

    assert metrics["runs"] == 2
    assert metrics["successes"] == 1
    assert metrics["failures"] == 1
    assert metrics["success_rate"] == 0.5


def test_health_reports_adapter_state():
    adapter = FakeERPAdapter()

    health = get_erp_health(adapter)

    assert health["status"] == "available"
    assert health["adapter"] == "FakeERPAdapter"
    assert health["invoice_count"] == 0


def test_trace_lookup_by_order_id():
    adapter = FakeERPAdapter()
    observability = ERPObservability()

    run_with_erp_adapter(
        sample_order(),
        adapter,
        observability,
    )

    trace = observability.get_trace("ORDER-OBS-TEST")

    assert len(trace) >= 4
    assert trace[0]["event"] == "integration.started"
    assert trace[-1]["event"] == "integration.completed"


def test_secret_redaction_is_recursive():
    data = {
        "api_key": "secret123",
        "user": {
            "password": "pass123",
            "name": "Test",
        },
    }

    safe = redact_secrets(data)

    assert safe["api_key"] == "***REDACTED***"
    assert safe["user"]["password"] == "***REDACTED***"
    assert safe["user"]["name"] == "Test"


def test_inventory_timeout_exposes_partial_state():
    adapter = FakeERPAdapter(failure_mode="inventory_timeout")
    observability = ERPObservability()

    result = run_with_erp_adapter(
        sample_order(),
        adapter,
        observability,
    )

    assert result["status"] == "failed"

    # Invoice was created before inventory synchronization failed.
    assert len(adapter.invoices) == 1
    assert len(adapter.inventory_updates) == 0


def test_task4_fixture_contains_evidence():
    evidence = run_task4_fixture()

    assert evidence["successful_run"]["status"] == "completed"
    assert evidence["failed_run"]["status"] == "failed"
    assert len(evidence["traces"]) > 0
    assert evidence["health"]["status"] == "available"
