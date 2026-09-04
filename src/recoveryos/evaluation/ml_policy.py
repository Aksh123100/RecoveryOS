import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from .world import ACTIONS, COSTS, Case, generate_cases, true_p, counterfactual_uniform

NUMERIC=["customer_previous_success_rate","merchant_recent_failure_rate","days_since_last_success","retry_count","time_since_failure"]
CATEGORICAL=["failure_code","device_type","time_of_day"]

class RecoveryMLPolicy:
    def __init__(self):
        self.models={}
        for action in ACTIONS:
            pre=ColumnTransformer([("num",StandardScaler(),NUMERIC),("cat",OneHotEncoder(handle_unknown="ignore"),CATEGORICAL)])
            self.models[action]=Pipeline([("pre",pre),("model",LogisticRegression(max_iter=1000,class_weight="balanced"))])
    def fit(self, cases, outcome_seed=7001):
        rows=pd.DataFrame([c.to_features() for c in cases])
        for action in ACTIONS:
            y=np.array([counterfactual_uniform(c.case_id,action,outcome_seed)<true_p(c,action) for c in cases],dtype=int)
            self.models[action].fit(rows,y)
        return self
    def predict_probabilities(self, case):
        row=pd.DataFrame([case.to_features()])
        return {a:float(np.clip(self.models[a].predict_proba(row)[0,1],.001,.999)) for a in ACTIONS}
    def choose(self, case, allowed=ACTIONS):
        p=self.predict_probabilities(case)
        scores={a:p[a]*case.amount-COSTS[a] for a in allowed}
        return max(scores,key=scores.get),p
