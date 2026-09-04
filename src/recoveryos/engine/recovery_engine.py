from recoveryos.evaluation.world import ACTIONS,COSTS,true_p,counterfactual_uniform
from .policy import RecoveryPolicy
class RecoveryEngine:
    def __init__(self,ml_model,agent,policy,audit,ambiguity_margin=.02):
        self.ml_model=ml_model; self.agent=agent; self.policy=policy; self.audit=audit; self.ambiguity_margin=ambiguity_margin
    def _rules(self,case):
        if case.failure_code=="EXPIRED_CODE": return ["request_alternate_method"]
        if case.failure_code=="INSUFFICIENT_FUNDS_CODE": return ["retry_later"]
        return None
    def decide(self,case):
        rule=self._rules(case)
        if rule:
            self.audit.record("rule_decision",case_id=case.case_id,ranked_actions=rule)
            return rule,{"source":"rule","agent_invoked":False}
        allowed=[a for a in ACTIONS if self.policy.check(case,a).allowed]
        if not allowed: return None,{"source":"policy","agent_invoked":False}
        _,probs=self.ml_model.choose(case.to_feature_case(),tuple(allowed))
        ranked=sorted(allowed,key=lambda a:probs[a]*case.amount-COSTS[a],reverse=True)
        vals=[probs[a]*case.amount-COSTS[a] for a in ranked]
        ambiguous=len(vals)>1 and (vals[0]-vals[1])/max(case.amount,1.0)<self.ambiguity_margin
        self.audit.record("ml_decision",case_id=case.case_id,probabilities=probs,ranked_actions=ranked,ambiguous=ambiguous)
        if not ambiguous: return ranked,{"source":"ml","agent_invoked":False,"probabilities":probs}
        if case.agent_invoked:
            return ranked,{"source":"ml","agent_invoked":False,"probabilities":probs}
        case.agent_invoked=True
        proposal=self.agent.investigate(case)
        pr=[a for a in proposal.get("ranked_actions",[]) if a in allowed]
        pr += [a for a in ranked if a not in pr]
        self.audit.record("agent_decision",case_id=case.case_id,proposal=proposal,agent_invoked=True)
        return pr,{"source":"agent","agent_invoked":True,"probabilities":probs,"proposal":proposal}
    def run_case(self,case,seed=1000,max_steps=3):
        agent_invocations=0
        for _ in range(max_steps):
            ranked,meta=self.decide(case)
            agent_invocations += int(meta.get("agent_invoked",False))
            if not ranked:
                case.status="STOPPED"; case.stop_reason="no_allowed_action"; return case
            action,blocked=self.policy.filter_ranked(case,ranked)
            if action is None:
                case.status="ESCALATED"; case.stop_reason="all_actions_blocked"
                self.audit.record("escalated",case_id=case.case_id,blocked=blocked); return case
            self.audit.record("action_attempted",case_id=case.case_id,action=action,blocked=blocked)
            fc=case.to_feature_case()
            success=counterfactual_uniform(fc.case_id,action,seed)<true_p(fc,action)
            case.actions_attempted.append(action); case.outcome_history.append({"action":action,"success":bool(success)})
            if success:
                case.status="RECOVERED"; self.audit.record("recovered",case_id=case.case_id,action=action,amount=case.amount); return case
            if action in {"retry_now","retry_later"}: case.episode_retry_count += 1
            self.audit.record("action_failed",case_id=case.case_id,action=action)
        case.status="STOPPED"; case.stop_reason="max_steps_reached"
        self.audit.record("stopped",case_id=case.case_id,reason=case.stop_reason)
        return case
