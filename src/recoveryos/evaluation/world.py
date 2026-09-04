from dataclasses import dataclass
import hashlib
import numpy as np

ACTIONS = ("retry_now","retry_later","request_alternate_method")
COSTS = {"retry_now":0.20,"retry_later":0.20,"request_alternate_method":1.50}

STATES = {
"temporary_liquidity":{"prior":.26,"emission":{"TIMEOUT":.30,"DECLINED":.10,"INSUFFICIENT_FUNDS_CODE":.60},"p":{"retry_now":.30,"retry_later":.75,"request_alternate_method":.40},"success_rate":.78,"merchant_failure":.08,"retry_lambda":1.1},
"bank_degradation":{"prior":.22,"emission":{"TIMEOUT":.50,"DECLINED":.30,"NETWORK_ERROR":.20},"p":{"retry_now":.25,"retry_later":.70,"request_alternate_method":.45},"success_rate":.90,"merchant_failure":.28,"retry_lambda":.8},
"expired_method":{"prior":.16,"emission":{"TIMEOUT":.10,"DECLINED":.20,"EXPIRED_CODE":.70},"p":{"retry_now":.05,"retry_later":.08,"request_alternate_method":.88},"success_rate":.72,"merchant_failure":.06,"retry_lambda":1.0},
"hard_decline":{"prior":.14,"emission":{"TIMEOUT":.20,"DECLINED":.80},"p":{"retry_now":.02,"retry_later":.03,"request_alternate_method":.18},"success_rate":.48,"merchant_failure":.05,"retry_lambda":2.0},
"user_abandonment":{"prior":.22,"emission":{"TIMEOUT":.70,"NO_ATTEMPT":.30},"p":{"retry_now":.22,"retry_later":.35,"request_alternate_method":.58},"success_rate":.83,"merchant_failure":.07,"retry_lambda":.4}
}

@dataclass(frozen=True)
class Case:
    case_id:int
    hidden_state:str
    failure_code:str
    amount:float
    customer_previous_success_rate:float
    merchant_recent_failure_rate:float
    days_since_last_success:float
    retry_count:int
    time_since_failure:float
    device_type:str
    time_of_day:str
    def to_features(self):
        return {"failure_code":self.failure_code,"customer_previous_success_rate":self.customer_previous_success_rate,
        "merchant_recent_failure_rate":self.merchant_recent_failure_rate,"days_since_last_success":self.days_since_last_success,
        "retry_count":self.retry_count,"time_since_failure":self.time_since_failure,
        "device_type":self.device_type,"time_of_day":self.time_of_day}

def generate_cases(n=1000, seed=42):
    rng=np.random.default_rng(seed); states=list(STATES)
    pri=np.array([STATES[s]["prior"] for s in states]); out=[]
    for i in range(n):
        s=states[int(rng.choice(len(states),p=pri/pri.sum()))]; spec=STATES[s]
        codes=list(spec["emission"]); ws=np.array(list(spec["emission"].values()))
        code=codes[int(rng.choice(len(codes),p=ws/ws.sum()))]
        out.append(Case(
            i,s,code,float(np.clip(np.exp(rng.normal(np.log(1800),.85)),50,50000)),
            float(np.clip(rng.normal(spec["success_rate"],.13),.02,.99)),
            float(np.clip(rng.normal(spec["merchant_failure"],.09),0,.75)),
            float(np.clip(rng.gamma(2,2),.1,30)),
            int(np.clip(rng.poisson(spec["retry_lambda"]),0,5)),
            float(np.clip(rng.lognormal(np.log(18),.7),.2,240)),
            str(rng.choice(["android","ios","web"],p=[.5,.25,.25])),
            str(rng.choice(["morning","afternoon","evening","night"]))
        ))
    return out

def true_p(case, action):
    p=STATES[case.hidden_state]["p"][action]
    if action=="retry_later": p += .08*case.merchant_recent_failure_rate + .05*(1-case.customer_previous_success_rate)
    if action=="request_alternate_method": p += .08*(1-case.customer_previous_success_rate)
    if case.retry_count>=3 and action in {"retry_now","retry_later"}: p -= .12
    if case.time_since_failure>48 and action=="retry_now": p -= .03
    return float(np.clip(p,.01,.98))

def counterfactual_uniform(case_id, action, seed):
    d=hashlib.sha256(f"{case_id}|{action}|{seed}".encode()).digest()
    return int.from_bytes(d[:8],"big")/(2**64)
