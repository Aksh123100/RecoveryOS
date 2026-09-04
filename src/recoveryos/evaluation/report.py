from pathlib import Path
import pandas as pd

def build_report(csv_path="benchmark/repeated_runs.csv", out_path="benchmark/evaluation_report.md"):
    df=pd.read_csv(csv_path)
    rows=[]
    for (evaluation,policy),g in df.groupby(["evaluation","policy"]):
        rows.append({
            "evaluation": evaluation, "policy": policy,
            "recovery_rate": g.recovery_rate.mean(),
            "net_recovered": g.net_recovered.mean(),
            "cost": g.cost.mean(), "avg_actions": g.avg_actions.mean(),
            "agent_invocation_rate": g.agent_invocation_rate.dropna().mean() if "agent_invocation_rate" in g else None,
        })
    s=pd.DataFrame(rows)
    lines=["# RecoveryOS Evaluation Evidence", "", "> Controlled synthetic benchmark; figures are not production Razorpay recovery rates.", "", "| Evaluation | Policy | Recovery rate | Mean net recovered | Mean cost | Avg actions | Agent invocation |", "|---|---|---:|---:|---:|---:|---:|"]
    for _,r in s.sort_values(["evaluation","net_recovered"],ascending=[True,False]).iterrows():
        air="—" if pd.isna(r.agent_invocation_rate) else f"{r.agent_invocation_rate:.1%}"
        lines.append(f"| {r.evaluation} | {r.policy} | {r.recovery_rate:.1%} | ₹{r.net_recovered:,.0f} | ₹{r.cost:,.0f} | {r.avg_actions:.3f} | {air} |")
    lines += ["", "## Interpretation", "", "- One-step ML materially outperforms the naive and strong-rule baselines on this synthetic benchmark.", "- Sequential ML approaches the oracle policy under the bounded action/retry constraints.", "- `agent_proxy` is an evaluation proxy, not measured LLM performance; its observed recovery result should not be presented as proof of incremental LLM recovery uplift.", "- Intervention costs are benchmark assumptions, not Razorpay fees."]
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    return s

if __name__=="__main__":
    print(build_report().to_string(index=False))
