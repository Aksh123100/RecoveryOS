from functools import lru_cache
from .world import ACTIONS,COSTS,true_p,counterfactual_uniform

def oracle_sequence(case):
    rem=tuple(ACTIONS)
    @lru_cache(None)
    def V(rem,retries,contacts):
        best=0.0
        for a in rem:
            if a in {"retry_now","retry_later"} and retries>=2: continue
            if a=="request_alternate_method" and contacts>=1: continue
            nxt=tuple(x for x in rem if x!=a)
            nr=retries+int(a in {"retry_now","retry_later"})
            nc=contacts+int(a=="request_alternate_method")
            p=true_p(case,a)
            best=max(best,-COSTS[a]+p*case.amount+(1-p)*V(nxt,nr,nc))
        return best
    vals=[]
    for a in rem:
        nxt=tuple(x for x in rem if x!=a)
        p=true_p(case,a)
        q=-COSTS[a]+p*case.amount+(1-p)*V(nxt,int(a in {"retry_now","retry_later"}),int(a=="request_alternate_method"))
        vals.append((q,a))
    return [a for _,a in sorted(vals,reverse=True)]

def run_oracle(cases,seed, sequences=None):
    gross=cost=0.0; recovered=actions=0
    if sequences is None:
        sequences=[oracle_sequence(c) for c in cases]
    for c, seq in zip(cases, sequences):
        for a in seq:
            actions+=1; cost+=COSTS[a]
            if counterfactual_uniform(c.case_id,a,seed)<true_p(c,a):
                gross+=c.amount; recovered+=1; break
    return {"recovery_rate":recovered/len(cases),"gross_recovered":gross,"cost":cost,
            "net_recovered":gross-cost,"avg_actions":actions/len(cases)}
