from dataclasses import dataclass,field
@dataclass
class RecoveryCase:
    case_id:str
    amount:float
    failure_code:str
    customer_previous_success_rate:float
    merchant_recent_failure_rate:float
    days_since_last_success:float
    retry_count:int
    time_since_failure:float
    device_type:str="unknown"
    time_of_day:str="unknown"
    episode_retry_count:int=0
    contact_count:int=0
    agent_invoked:bool=False
    actions_attempted:list=field(default_factory=list)
    outcome_history:list=field(default_factory=list)
    status:str="OPEN"
    stop_reason:str|None=None
    def to_feature_case(self):
        from recoveryos.evaluation.world import Case
        cid=int(self.case_id) if str(self.case_id).isdigit() else abs(hash(self.case_id))%10000000
        return Case(cid,"temporary_liquidity",self.failure_code,self.amount,self.customer_previous_success_rate,
                    self.merchant_recent_failure_rate,self.days_since_last_success,self.retry_count,self.time_since_failure,
                    self.device_type,self.time_of_day)
