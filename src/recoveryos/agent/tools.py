import json
class AgentToolbox:
    def __init__(self,ml_model): self.ml_model=ml_model
    def get_payment_history(self,case):
        return {"failure_code":case.failure_code,"historical_retry_count":case.retry_count,
                "episode_retry_count":case.episode_retry_count,"recent_outcomes":case.outcome_history[-3:],
                "customer_success_rate":case.customer_previous_success_rate}
    def get_merchant_health(self,case):
        return {"recent_failure_rate":case.merchant_recent_failure_rate,
                "possible_degradation":case.merchant_recent_failure_rate>=.20}
    def predict_recovery(self,case):
        return self.ml_model.predict_probabilities(case.to_feature_case())
    def schemas(self):
        blank={"type":"object","properties":{},"additionalProperties":False}
        return [
            {"type":"function","function":{"name":"get_payment_history","description":"Inspect case retry and outcome history","parameters":blank}},
            {"type":"function","function":{"name":"get_merchant_health","description":"Inspect merchant recent failure health","parameters":blank}},
            {"type":"function","function":{"name":"predict_recovery","description":"Get ML P(recovery|action)","parameters":blank}}
        ]
class SelectiveRecoveryAgent:
    def __init__(self,provider,toolbox,max_tool_rounds=3):
        self.provider=provider; self.toolbox=toolbox; self.max_tool_rounds=max_tool_rounds
    def investigate(self,case):
        messages=[{"role":"user","content":(
            f"Case ₹{case.amount:.2f}; failure={case.failure_code}; historical_retry_count={case.retry_count}; "
            f"episode_retry_count={case.episode_retry_count}; merchant_failure_rate={case.merchant_recent_failure_rate:.2f}; "
            f"customer_success_rate={case.customer_previous_success_rate:.2f}. Investigate and rank actions."
        )}]
        for _ in range(self.max_tool_rounds):
            result=self.provider.complete(messages,self.toolbox.schemas())
            if isinstance(result,dict) and "ranked_actions" in result: return result
            calls=result.get("tool_calls",[]) if isinstance(result,dict) else []
            if not calls:
                return json.loads(result.get("content","{}"))
            messages.append(result)
            for call in calls:
                name=call["function"]["name"]; args=call["function"].get("arguments","{}")
                if isinstance(args,str): args=json.loads(args)
                out=getattr(self.toolbox,name)(case)
                messages.append({"role":"tool","tool_call_id":call["id"],"name":name,"content":json.dumps(out)})
        raise RuntimeError("agent_tool_round_limit")
