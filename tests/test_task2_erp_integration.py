
import pytest

from erp_integration import (
    FakeERPSystem,
    synchronize_paid_order,
    run_task2_fixture,
)


def valid_order():
    return {
        "order_id": "ORDER-TEST-2001",
        "customer_id": "CUST-TEST-01",
        "customer_name": "Test Customer",
        "customer_email": "test@example.com",
        "payment_status": "paid",
        "currency": "INR",
        "items": [
            {
                "sku": "SKU-001",
                "name": "Keyboard",
                "quantity": 2,
                "unit_price": 1000,
            }
        ],
    }


def test_successful_erp_synchronization():
    erp = FakeERPSystem()

    result = synchronize_paid_order(valid_order(), erp)

    assert result["status"] == "completed"
    assert result["source_order_id"] == "ORDER-TEST-2001"
    assert len(erp.invoices) == 1
    assert len(erp.inventory_updates) == 1


def test_invoice_field_mapping_and_total():
    erp = FakeERPSystem()

    result = synchronize_paid_order(valid_order(), erp)

    invoice = result["invoice"]

    assert invoice["customer_code"] == "CUST-TEST-01"
    assert invoice["customer_name"] == "Test Customer"
    assert invoice["total_amount"] == 2000.0
    assert invoice["lines"][0]["item_code"] == "SKU-001"


def test_inventory_quantity_synchronization():
    erp = FakeERPSystem()

    result = synchronize_paid_order(valid_order(), erp)

    assert result["inventory"]["quantities"] == {"SKU-001": 2}
    assert erp.inventory["SKU-001"] == 98

def test_unpaid_order_is_rejected():
    erp = FakeERPSystem()
    order = valid_order()
    order["payment_status"] = "pending"

    result = synchronize_paid_order(order, erp)

    assert result["status"] == "failed"
    assert "payment" in result["error"].lower()
    assert len(erp.invoices) == 0
    assert len(erp.inventory_updates) == 0


def test_missing_customer_is_rejected():
    erp = FakeERPSystem()
    order = valid_order()
    order["customer_id"] = ""

    result = synchronize_paid_order(order, erp)

    assert result["status"] == "failed"
    assert len(erp.invoices) == 0


def test_empty_order_items_are_rejected():
    erp = FakeERPSystem()
    order = valid_order()
    order["items"] = []

    result = synchronize_paid_order(order, erp)

    assert result["status"] == "failed"
    assert len(erp.invoices) == 0


def test_invalid_item_quantity_is_rejected():
    erp = FakeERPSystem()
    order = valid_order()
    order["items"][0]["quantity"] = -2

    result = synchronize_paid_order(order, erp)

    assert result["status"] == "failed"
    assert "quantity" in result["error"].lower()
    assert len(erp.invoices) == 0


def test_fixture_generates_expected_invoice():
    evidence = run_task2_fixture()

    result = evidence["result"]

    assert result["status"] == "completed"
    assert result["invoice"]["total_amount"] == 92250.0
    assert result["inventory"]["items_updated"] == 2
    assert len(evidence["erp_state"]["invoices"]) == 1
