# RecoveryOS Evaluation Evidence

> Controlled synthetic benchmark; figures are not production Razorpay recovery rates.

| Evaluation | Policy | Recovery rate | Mean net recovered | Mean cost | Avg actions | Agent invocation |
|---|---|---:|---:|---:|---:|---:|
| one_step | ml | 56.6% | ₹1,527,399 | ₹723 | 1.000 | — |
| one_step | strong_rules | 49.2% | ₹1,304,879 | ₹550 | 1.000 | — |
| one_step | naive | 18.3% | ₹500,560 | ₹200 | 1.000 | — |
| sequential | oracle | 78.8% | ₹2,118,713 | ₹998 | 1.732 | — |
| sequential | ml | 78.8% | ₹2,118,563 | ₹1,147 | 1.749 | — |
| sequential | agent_proxy | 78.8% | ₹2,118,560 | ₹1,151 | 1.744 | 13.4% |

## Interpretation

- One-step ML materially outperforms the naive and strong-rule baselines on this synthetic benchmark.
- Sequential ML approaches the oracle policy under the bounded action/retry constraints.
- `agent_proxy` is an evaluation proxy, not measured LLM performance; its observed recovery result should not be presented as proof of incremental LLM recovery uplift.
- Intervention costs are benchmark assumptions, not Razorpay fees.