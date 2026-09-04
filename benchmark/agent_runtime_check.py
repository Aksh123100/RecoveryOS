from recoveryos.evaluation.world import generate_cases
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.agent.providers import MockProvider
from recoveryos.agent.tools import AgentToolbox, SelectiveRecoveryAgent
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.recovery_engine import RecoveryEngine
from recoveryos.audit.logger import AuditLogger

c = generate_cases(1, 42)[0]
case = RecoveryCase(str(c.case_id), c.amount, "TIMEOUT", c.customer_previous_success_rate,
                    c.merchant_recent_failure_rate, c.days_since_last_success, c.retry_count,
                    c.time_since_failure, c.device_type, c.time_of_day)
model = RecoveryMLPolicy().fit(generate_cases(1500, 7))
provider = MockProvider(use_tools=True)
audit = AuditLogger()
agent = SelectiveRecoveryAgent(provider, AgentToolbox(model))
engine = RecoveryEngine(model, agent, RecoveryPolicy(max_episode_retries=1), audit, ambiguity_margin=1.0)
engine.run_case(case, seed=1001, max_steps=2)
print("agent_decision_events:", sum(e["event_type"] == "agent_decision" for e in audit.events))
print("action_events:", sum(e["event_type"] == "action_attempted" for e in audit.events))
print("outcome:", case.status)
print("event_types:", [e["event_type"] for e in audit.events])
