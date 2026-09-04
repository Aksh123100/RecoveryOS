
from recoveryos.evaluation.world import generate_cases
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.razorpay_workflow import RazorpayRecoveryWorkflow
from recoveryos.audit.logger import AuditLogger
from recoveryos.agent.providers import MockProvider
from recoveryos.agent.tools import AgentToolbox, SelectiveRecoveryAgent

def make(c, code):
    return RecoveryCase(str(c.case_id), c.amount, code, c.customer_previous_success_rate, c.merchant_recent_failure_rate,
                        c.days_since_last_success, c.retry_count, c.time_since_failure, c.device_type, c.time_of_day)

def test_clear_rule_skips_ml_and_agent():
    cs=generate_cases(5,42); m=RecoveryMLPolicy().fit(generate_cases(1500,7)); a=AuditLogger()
    wf=RazorpayRecoveryWorkflow(m, RecoveryPolicy(), a)
    r=wf.handle_case(make(cs[0], "EXPIRED_CODE"))
    assert r.source=="rule" and r.action=="request_alternate_method"
    assert not any(e["event_type"]=="ml_decision" for e in a.events)
    assert not any(e["event_type"]=="agent_decision" for e in a.events)

def test_unclear_confident_uses_ml():
    cs=generate_cases(5,43); m=RecoveryMLPolicy().fit(generate_cases(1500,7)); a=AuditLogger()
    wf=RazorpayRecoveryWorkflow(m, RecoveryPolicy(), a, ambiguity_margin=-1.0)
    r=wf.handle_case(make(cs[0], "TIMEOUT"))
    assert r.source=="ml"

def test_ambiguous_uses_agent_then_policy():
    cs=generate_cases(5,44); m=RecoveryMLPolicy().fit(generate_cases(1500,7)); a=AuditLogger()
    provider=MockProvider(use_tools=True)
    agent=SelectiveRecoveryAgent(provider, AgentToolbox(m))
    wf=RazorpayRecoveryWorkflow(m, RecoveryPolicy(), a, agent=agent, ambiguity_margin=10.0)
    r=wf.handle_case(make(cs[0], "TIMEOUT"))
    assert r.source=="agent"
    assert any(e["event_type"]=="agent_decision" for e in a.events)
    assert any(e["event_type"]=="action_selected" for e in a.events)
