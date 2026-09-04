from recoveryos.evaluation.world import generate_cases
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.agent.providers import MockProvider
from recoveryos.agent.tools import AgentToolbox,SelectiveRecoveryAgent
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.recovery_engine import RecoveryEngine
from recoveryos.audit.logger import AuditLogger

def make_case():
    c=generate_cases(1,41)[0]
    return RecoveryCase(str(c.case_id),c.amount,"TIMEOUT",c.customer_previous_success_rate,c.merchant_recent_failure_rate,
                        c.days_since_last_success,c.retry_count,c.time_since_failure,c.device_type,c.time_of_day)

def test_actual_ml():
    model=RecoveryMLPolicy().fit(generate_cases(1200,123))
    p=model.predict_probabilities(generate_cases(1,999)[0])
    assert set(p)=={"retry_now","retry_later","request_alternate_method"}
    assert all(0<x<1 for x in p.values())

def test_agent_uses_ml_tool():
    model=RecoveryMLPolicy().fit(generate_cases(1500,7))
    agent=SelectiveRecoveryAgent(MockProvider(),AgentToolbox(model))
    result=agent.investigate(make_case())
    assert result["ranked_actions"]

def test_policy_gate_stays_outside_agent():
    model=RecoveryMLPolicy().fit(generate_cases(1500,7))
    agent=SelectiveRecoveryAgent(MockProvider(preferred="retry_now"),AgentToolbox(model))
    audit=AuditLogger()
    engine=RecoveryEngine(model,agent,RecoveryPolicy(max_episode_retries=0),audit,ambiguity_margin=10.0)
    engine.run_case(make_case(),seed=1002,max_steps=1)
    assert not any(e.get("event_type")=="action_attempted" and e.get("action")=="retry_now" for e in audit.events)

def test_retry_semantics():
    c=make_case(); c.retry_count=4; assert c.episode_retry_count==0
    c.episode_retry_count=1; assert c.retry_count==4
