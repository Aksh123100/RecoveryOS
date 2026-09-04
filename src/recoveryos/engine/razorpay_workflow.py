from dataclasses import dataclass

from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.audit.logger import AuditLogger
from recoveryos.agent.tools import AgentToolbox, SelectiveRecoveryAgent
from recoveryos.agent.providers import MockProvider


@dataclass
class WorkflowResult:
    case: RecoveryCase
    source: str
    action: str | None
    blocked_reason: str | None = None
    execution: object | None = None
    observation: dict | None = None


class RazorpayRecoveryWorkflow:
    """Webhook -> rules/ML -> agent-on-ambiguity -> policy -> execution -> observe."""

    def __init__(
        self,
        ml_model: RecoveryMLPolicy,
        policy: RecoveryPolicy,
        audit: AuditLogger | None = None,
        agent=None,
        ambiguity_margin: float = 0.02,
        executor=None,
    ):
        self.ml_model = ml_model
        self.policy = policy
        self.audit = audit or AuditLogger()
        self.agent = agent or SelectiveRecoveryAgent(MockProvider(use_tools=True), AgentToolbox(ml_model))
        self.ambiguity_margin = ambiguity_margin
        self.executor = executor

    def _rules(self, case: RecoveryCase):
        if case.failure_code == "EXPIRED_CODE":
            return ["request_alternate_method"]
        if case.failure_code == "INSUFFICIENT_FUNDS_CODE":
            return ["retry_later"]
        return None

    def handle_case(self, case: RecoveryCase) -> WorkflowResult:
        ranked = self._rules(case)
        source = "rule"
        probs = None

        if ranked is None:
            fc = case.to_feature_case()
            allowed = [
                a for a in ("retry_now", "retry_later", "request_alternate_method")
                if self.policy.check(case, a).allowed
            ]
            if not allowed:
                self.audit.record("stopped", case_id=case.case_id, reason="no_allowed_action")
                case.status = "STOPPED"
                case.stop_reason = "no_allowed_action"
                return WorkflowResult(case, "policy", None, "no_allowed_action")

            _, probs = self.ml_model.choose(fc, tuple(allowed))
            costs = {"retry_now": 0.20, "retry_later": 0.20, "request_alternate_method": 1.50}
            ranked = sorted(allowed, key=lambda a: probs[a] * case.amount - costs[a], reverse=True)
            source = "ml"
            vals = [probs[a] * case.amount - costs[a] for a in ranked]
            ambiguous = len(vals) > 1 and (vals[0] - vals[1]) / max(case.amount, 1.0) < self.ambiguity_margin
            self.audit.record(
                "ml_decision",
                case_id=case.case_id,
                probabilities=probs,
                ranked_actions=ranked,
                ambiguous=ambiguous,
            )

            if ambiguous and not case.agent_invoked:
                case.agent_invoked = True
                proposal = self.agent.investigate(case)
                proposed = [a for a in proposal.get("ranked_actions", []) if a in allowed]
                proposed += [a for a in ranked if a not in proposed]
                ranked = proposed
                source = "agent"
                self.audit.record("agent_decision", case_id=case.case_id, proposal=proposal, agent_invoked=True)

        self.audit.record("decision", case_id=case.case_id, source=source, ranked_actions=ranked)
        action, blocked = self.policy.filter_ranked(case, ranked)
        if action is None:
            case.status = "ESCALATED"
            case.stop_reason = "all_actions_blocked"
            self.audit.record("escalated", case_id=case.case_id, blocked=blocked)
            return WorkflowResult(case, source, None, "all_actions_blocked")

        self.audit.record(
            "action_selected",
            case_id=case.case_id,
            source=source,
            action=action,
            blocked=blocked,
            probabilities=probs,
        )

        if self.executor is None:
            return WorkflowResult(case, source, action, execution=None, observation=None)

        self.audit.record("action_attempted", case_id=case.case_id, action=action, blocked=blocked)
        execution = self.executor.execute(case, action)
        case.actions_attempted.append(action)
        self.audit.record(
            "action_executed",
            case_id=case.case_id,
            action=action,
            status=execution.status,
            order_id=execution.order_id,
            detail=execution.detail,
        )
        observation = self.executor.observe(execution)
        self.audit.record("observation", case_id=case.case_id, action=action, observation=observation)

        if observation.get("status") == "RECOVERED":
            case.status = "RECOVERED"
            self.audit.record("recovered", case_id=case.case_id, action=action, amount=case.amount)
        elif execution.status == "SCHEDULED":
            case.status = "OPEN"
        else:
            case.status = "OPEN"

        return WorkflowResult(case, source, action, execution=execution, observation=observation)
