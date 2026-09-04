import numpy as np
import pandas as pd
from .world import ACTIONS,COSTS,generate_cases,counterfactual_uniform,true_p
from .baselines import naive,strong_rules
from .ml_policy import RecoveryMLPolicy
from .oracle import run_oracle,oracle_sequence

def choose_ml(c, probs, allowed):
    return max(allowed,key=lambda a:probs[c.case_id][a]*c.amount-COSTS[a])

def choose_agent_proxy(c, probs, allowed):
    # Offline evaluation proxy for the agent: uses the same ML tool output plus
    # merchant/customer context. It is NOT a measured LLM performance result.
    scored={a:probs[c.case_id][a]*c.amount-COSTS[a] for a in allowed}
    if c.merchant_recent_failure_rate>=.20 and "retry_later" in allowed:
        scored["retry_later"] += .05*c.amount
    if c.customer_previous_success_rate<.65 and "request_alternate_method" in allowed:
        scored["request_alternate_method"] += .04*c.amount
    return max(scored,key=scored.get)

def ambiguous(c, probs, margin=.02):
    vals=sorted([probs[c.case_id][a]*c.amount-COSTS[a] for a in ACTIONS],reverse=True)
    return len(vals)>1 and (vals[0]-vals[1])/max(c.amount,1.0)<margin

def run_one_step(cases, chooser, seed):
    gross=cost=0.0; recovered=0
    for c in cases:
        a=chooser(c)
        cost+=COSTS[a]
        if counterfactual_uniform(c.case_id,a,seed)<true_p(c,a):
            gross+=c.amount; recovered+=1
    return recovered/len(cases),gross,cost,gross-cost

def run_sequential(cases, chooser_factory, seed, max_steps=3):
    gross=cost=0.0; recovered=actions=0
    for c in cases:
        attempted=[]; live_retries=0
        for _ in range(max_steps):
            allowed=[a for a in ACTIONS if a not in attempted and not(a in {"retry_now","retry_later"} and live_retries>=2)]
            if not allowed: break
            a=chooser_factory(c,allowed,attempted,live_retries)
            attempted.append(a); actions+=1; cost+=COSTS[a]
            if counterfactual_uniform(c.case_id,a,seed)<true_p(c,a):
                gross+=c.amount; recovered+=1; break
            if a in {"retry_now","retry_later"}: live_retries+=1
    return recovered/len(cases),gross,cost,gross-cost,actions/len(cases)

def repeated(n_cases=1000,n_seeds=50):
    train=generate_cases(8000,1234); bench=generate_cases(n_cases,42)
    model=RecoveryMLPolicy().fit(train)
    probs={c.case_id:model.predict_probabilities(c) for c in bench}
    oracle_sequences=[oracle_sequence(c) for c in bench]
    rows=[]; agent_invocations=sum(ambiguous(c,probs) for c in bench)
    agent_rate=agent_invocations/len(bench)
    for seed in range(1000,1000+n_seeds):
        for name,fn in [("naive",lambda c:naive(c)),("strong_rules",lambda c:strong_rules(c)),("ml",lambda c:choose_ml(c,probs,ACTIONS))]:
            r,g,cost,net=run_one_step(bench,fn,seed)
            rows.append({"seed":seed,"evaluation":"one_step","policy":name,"recovery_rate":r,"gross_recovered":g,"cost":cost,"net_recovered":net,"avg_actions":1.0})
        r,g,cost,net,aa=run_sequential(bench,lambda c,a,attempted,retries: choose_ml(c,probs,a),seed)
        rows.append({"seed":seed,"evaluation":"sequential","policy":"ml","recovery_rate":r,"gross_recovered":g,"cost":cost,"net_recovered":net,"avg_actions":aa})
        r,g,cost,net,aa=run_sequential(bench,lambda c,a,attempted,retries: choose_agent_proxy(c,probs,a) if ambiguous(c,probs) else choose_ml(c,probs,a),seed)
        rows.append({"seed":seed,"evaluation":"sequential","policy":"agent_proxy","recovery_rate":r,"gross_recovered":g,"cost":cost,"net_recovered":net,"avg_actions":aa,"agent_invocation_rate":agent_rate})
        o=run_oracle(bench,seed,oracle_sequences)
        rows.append({"seed":seed,"evaluation":"sequential","policy":"oracle",**{"recovery_rate":o["recovery_rate"],"gross_recovered":o["gross_recovered"],"cost":o["cost"],"net_recovered":o["net_recovered"],"avg_actions":o["avg_actions"]}})
    df=pd.DataFrame(rows)
    summaries=[]
    for (ev,pol),g in df.groupby(["evaluation","policy"]):
        x=g.net_recovered.to_numpy(); m=x.mean(); sd=x.std(ddof=1); se=sd/np.sqrt(len(x))
        summaries.append({"evaluation":ev,"policy":pol,"mean_net_recovered":m,"ci95_low":m-1.96*se,"ci95_high":m+1.96*se,"mean_recovery_rate":g.recovery_rate.mean(),"mean_cost":g.cost.mean(),"mean_avg_actions":g.avg_actions.mean()})
    summary=pd.DataFrame(summaries).sort_values(["evaluation","mean_net_recovered"],ascending=[True,False])
    return df,summary,model,agent_rate
