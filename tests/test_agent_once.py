from recoveryos.evaluation.world import generate_cases
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.agent.providers import MockProvider
from recoveryos.agent.tools import AgentToolbox, SelectiveRecoveryAgent
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.recovery_engine import RecoveryEngine
from recoveryos.audit.logger import AuditLogger

def test_agent_invoked_at_most_once_per_case():
    c=generate_cases(1,42)[0]
    case=RecoveryCase(str(c.case_id),c.amount,"TIMEOUT",c.customer_previous_success_rate,c.merchant_recent_failure_rate,
                      c.days_since_last_success,c.retry_count,c.time_since_failure,c.device_type,c.time_of_day)
    model=RecoveryMLPolicy().fit(generate_cases(1200,8))
    audit=AuditLogger(); provider=MockProvider(use_tools=True)
    agent=SelectiveRecoveryAgent(provider,AgentToolbox(model))
    engine=RecoveryEngine(model,agent,RecoveryPolicy(max_episode_retries=1),audit,ambiguity_margin=1.0)
    engine.run_case(case,seed=1002,max_steps=2)
    assert sum(e["event_type"]=="agent_decision" for e in audit.events) <= 1
