from dataclasses import dataclass
from recoveryos.evaluation.world import ACTIONS
@dataclass(frozen=True)
class PolicyDecision:
    allowed:bool
    reason:str
class RecoveryPolicy:
    def __init__(self,max_episode_retries=2,max_contacts=1):
        self.max_episode_retries=max_episode_retries; self.max_contacts=max_contacts
    def check(self,case,action):
        if action not in ACTIONS: return PolicyDecision(False,"unknown_action")
        if action in case.actions_attempted: return PolicyDecision(False,"action_already_attempted")
        if action in {"retry_now","retry_later"} and case.episode_retry_count>=self.max_episode_retries:
            return PolicyDecision(False,"retry_limit_reached")
        if action=="request_alternate_method" and case.contact_count>=self.max_contacts:
            return PolicyDecision(False,"contact_limit_reached")
        if case.failure_code in {"HARD_DECLINE","HARD_DECLINE_CODE"} and action in {"retry_now","retry_later"}:
            return PolicyDecision(False,"hard_decline_no_retry")
        return PolicyDecision(True,"allowed")
    def filter_ranked(self,case,ranked):
        blocked=[]
        for a in ranked:
            d=self.check(case,a)
            if d.allowed: return a,blocked
            blocked.append({"action":a,"reason":d.reason})
        return None,blocked
