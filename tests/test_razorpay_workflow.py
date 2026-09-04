from recoveryos.evaluation.world import generate_cases
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.razorpay_workflow import RazorpayRecoveryWorkflow
from recoveryos.audit.logger import AuditLogger

def mk(c, failure_code):
    return RecoveryCase(
        case_id=str(c.case_id), amount=c.amount, failure_code=failure_code,
        customer_previous_success_rate=c.customer_previous_success_rate,
        merchant_recent_failure_rate=c.merchant_recent_failure_rate,
        days_since_last_success=c.days_since_last_success,
        retry_count=c.retry_count, time_since_failure=c.time_since_failure,
        device_type=c.device_type, time_of_day=c.time_of_day,
    )

def test_webhook_case_uses_rule_before_ml():
    cases=generate_cases(10,55)
    model=RecoveryMLPolicy().fit(generate_cases(1800,7))
    audit=AuditLogger()
    flow=RazorpayRecoveryWorkflow(model, RecoveryPolicy(), audit)
    result=flow.handle_case(mk(cases[0], "EXPIRED_CODE"))
    assert result.source=="rule"
    assert result.action=="request_alternate_method"
    assert not any(e["event_type"]=="ml_decision" for e in audit.events)

def test_ambiguous_observable_case_uses_ml():
    cases=generate_cases(10,55)
    model=RecoveryMLPolicy().fit(generate_cases(1800,7))
    flow=RazorpayRecoveryWorkflow(model, RecoveryPolicy(), ambiguity_margin=-1.0)
    result=flow.handle_case(mk(cases[0], "TIMEOUT"))
    assert result.source=="ml"
    assert result.action in {"retry_now","retry_later","request_alternate_method"}

def test_policy_blocks_selected_action():
    cases=generate_cases(10,55)
    model=RecoveryMLPolicy().fit(generate_cases(1800,7))
    policy=RecoveryPolicy(max_episode_retries=0, max_contacts=0)
    flow=RazorpayRecoveryWorkflow(model, policy)
    c=mk(cases[0], "TIMEOUT")
    c.actions_attempted=["retry_later","request_alternate_method"]
    result=flow.handle_case(c)
    assert result.action=="retry_now" or result.action is None
