
import pytest

from erp_integration import (
    FakeERPSystem,
    run_erp_with_recovery,
    run_task3_fixture,
)


def sample_order(order_id="ORDER-REC-TEST"):
    return {
        "order_id": order_id,
        "customer_id": "CUST-REC",
        "customer_name": "Recovery Customer",
        "customer_email": "recovery@example.com",
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


def test_temporary_timeout_retries_and_completes():
    erp = FakeERPSystem()

    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="timeout_before_commit",
        max_retries=2,
    )

    assert result["status"] == "completed"
    assert result["attempts"] == 2
    assert len(erp.invoices) == 1
    assert len(erp.inventory_updates) == 1


def test_timeout_retry_limit_is_respected():
    erp = FakeERPSystem()

    # The implementation simulates one initial timeout.
    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="timeout_before_commit",
        max_retries=0,
    )

    assert result["status"] == "needs_review"
    assert result["attempts"] == 1
    assert len(erp.invoices) == 0


def test_malformed_response_is_not_retried():
    erp = FakeERPSystem()

    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="malformed_response",
    )

    assert result["status"] == "needs_review"
    assert result["attempts"] == 1
    assert len(erp.invoices) == 0


def test_permanent_failure_is_not_retried():
    erp = FakeERPSystem()

    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="permanent_failure",
    )

    assert result["status"] == "needs_review"
    assert result["attempts"] == 1
    assert len(erp.invoices) == 0


def test_duplicate_trigger_is_prevented():
    erp = FakeERPSystem()

    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="duplicate_trigger",
    )

    assert result["status"] == "duplicate_prevented"
    assert len(erp.invoices) == 0
    assert len(erp.inventory_updates) == 0


def test_timeout_after_commit_is_reconciled():
    erp = FakeERPSystem()

    result = run_erp_with_recovery(
        sample_order(),
        erp,
        scenario="timeout_after_commit",
    )

    assert result["status"] == "completed"
    assert result["reconciled"] is True
    assert len(erp.invoices) == 1
    assert len(erp.inventory_updates) == 1


def test_replay_after_completion_has_no_duplicate_side_effect():
    erp = FakeERPSystem()
    order = sample_order()

    first = run_erp_with_recovery(order, erp)
    second = run_erp_with_recovery(order, erp)

    assert first["status"] == "completed"
    assert second["status"] == "completed"
    assert second["replayed"] is True
    assert len(erp.invoices) == 1
    assert len(erp.inventory_updates) == 1


def test_negative_retry_limit_is_rejected():
    with pytest.raises(ValueError, match="max_retries"):
        run_erp_with_recovery(
            sample_order(),
            FakeERPSystem(),
            max_retries=-1,
        )


def test_recovery_fixture_contains_all_scenarios():
    evidence = run_task3_fixture()

    assert "success" in evidence
    assert "timeout_before_commit" in evidence
    assert "malformed_response" in evidence
    assert "permanent_failure" in evidence
    assert "timeout_after_commit" in evidence
    assert "replay_test" in evidence
