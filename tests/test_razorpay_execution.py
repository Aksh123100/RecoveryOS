from dataclasses import dataclass

from recoveryos.audit.logger import AuditLogger
from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.executor import ExecutionResult
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.razorpay_workflow import RazorpayRecoveryWorkflow
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.evaluation.world import generate_cases


@dataclass
class FakeExecutor:
    def execute(self, case, action):
        return ExecutionResult(action=action, status="ORDER_CREATED", order_id="order_test_1")

    def observe(self, execution):
        return {"status": "PENDING", "order_id": execution.order_id, "payment_count": 0}


def test_workflow_executes_and_observes_after_policy():
    source = generate_cases(1, 99)[0]
    case = RecoveryCase(
        case_id=str(source.case_id), amount=100.0, failure_code="EXPIRED_CODE",
        customer_previous_success_rate=source.customer_previous_success_rate,
        merchant_recent_failure_rate=source.merchant_recent_failure_rate,
        days_since_last_success=source.days_since_last_success,
        retry_count=source.retry_count,
        time_since_failure=source.time_since_failure,
        device_type=source.device_type,
        time_of_day=source.time_of_day,
    )
    audit = AuditLogger()
    model = RecoveryMLPolicy().fit(generate_cases(1500, 7))
    result = RazorpayRecoveryWorkflow(
        model, RecoveryPolicy(), audit, executor=FakeExecutor()
    ).handle_case(case)

    assert result.action == "request_alternate_method"
    assert result.execution.status == "ORDER_CREATED"
    assert result.observation["status"] == "PENDING"
    assert any(e["event_type"] == "action_executed" for e in audit.events)
    assert any(e["event_type"] == "observation" for e in audit.events)
