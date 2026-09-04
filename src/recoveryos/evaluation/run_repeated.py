from pathlib import Path
from .repeated import repeated

if __name__=="__main__":
    df,summary,_,agent_rate=repeated()
    out=Path("benchmark")
    out.mkdir(exist_ok=True)
    df.to_csv(out/"repeated_runs.csv",index=False)
    summary.to_csv(out/"summary.csv",index=False)
    (out/"agent_metrics.txt").write_text(f"ML ambiguity rate / agent invocation rate: {agent_rate:.4f}\n")
    print(summary.to_string(index=False))
    print(f"\nAgent invocation rate (benchmark proxy): {agent_rate:.2%}")
