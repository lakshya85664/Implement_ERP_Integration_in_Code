
import pytest

from erp_integration import (
    WorkflowRun,
    WorkflowState,
    WorkflowTask,
    TaskStatus,
    WorkflowInput,
    WorkflowResult,
    EventType,
    transition,
)


def create_run():
    return WorkflowRun(
        run_id="TEST-RUN-001",
        business_key="ORDER-TEST-001",
    )


def test_workflow_input_model():
    item = WorkflowInput(
        source_system="online_store",
        business_key="ORDER-TEST-001",
        payload={"payment_status": "paid"},
    )

    assert item.source_system == "online_store"
    assert item.business_key == "ORDER-TEST-001"


def test_workflow_run_initial_state():
    run = create_run()

    assert run.state == WorkflowState.CREATED
    assert run.attempts == 0
    assert run.events == []


def test_workflow_task_model():
    task = WorkflowTask(
        task_id="TASK-001",
        name="create_invoice",
    )

    assert task.status == TaskStatus.PENDING
    assert task.attempts == 0


def test_workflow_result_model():
    result = WorkflowResult(
        status=WorkflowState.COMPLETED,
        erp_invoice_id="INV-1001",
        inventory_reference="STOCK-1001",
    )

    assert result.erp_invoice_id == "INV-1001"
    assert result.inventory_reference == "STOCK-1001"


def test_legal_transition_created_to_running():
    run = create_run()

    transition(run, "start")

    assert run.state == WorkflowState.RUNNING
    assert run.events[-1].event_type == EventType.WORKFLOW_STARTED


def test_legal_transition_running_to_completed():
    run = create_run()
    transition(run, "start")

    transition(run, "complete")

    assert run.state == WorkflowState.COMPLETED
    assert run.events[-1].event_type == EventType.WORKFLOW_COMPLETED


def test_illegal_transition_is_rejected():
    run = create_run()

    with pytest.raises(ValueError, match="Illegal workflow transition"):
        transition(run, "complete")

    assert run.state == WorkflowState.CREATED


def test_pause_and_resume_transitions():
    run = create_run()

    transition(run, "start")
    transition(run, "pause")

    assert run.state == WorkflowState.WAITING

    transition(run, "resume")

    assert run.state == WorkflowState.RUNNING


def test_failure_moves_workflow_to_review():
    run = create_run()
    transition(run, "start")

    transition(run, "fail")

    assert run.state == WorkflowState.NEEDS_REVIEW


def test_event_trace_records_transition_details():
    run = create_run()

    transition(run, "start")

    assert len(run.events) == 1
    assert run.events[0].run_id == run.run_id
    assert run.events[0].details["transition"] == "start"
    assert run.events[0].details["new_state"] == "running"
