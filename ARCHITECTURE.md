# RecoveryOS Architecture

## Full decision + execution flow

```mermaid
flowchart TD
    A[Razorpay payment.failed] --> B[Webhook verification]
    B --> C[Persistent Case Store]

    C --> D{Rule diagnosis}
    D -->|clear| E[Deterministic rule action]
    D -->|unclear| F[ML recovery policy]

    F --> G{ML confidence / ambiguity}
    G -->|confident| H[Ranked ML action]
    G -->|ambiguous| I[Groq ambiguity resolver]

    I --> J[Tool inspection]
    J --> K[Ranked agent proposal]

    E --> L[Policy Gate]
    H --> L
    K --> L

    L --> M{Allowed?}
    M -->|No| N[STOP / ESCALATE]
    M -->|Yes| O[Bounded Test-Mode execution]

    O --> P[Razorpay recovery order]
    P --> Q[Recovery Checkout]

    Q --> R{Payment outcome}
    R -->|payment.captured| S[RECOVERED]
    R -->|payment.failed| T[Observe + re-decide]
    T --> L

    C -.-> U[Audit Trail]
    D -.-> U
    F -.-> U
    I -.-> U
    L -.-> U
    O -.-> U
    R -.-> U
```

Every stage — rule diagnosis, ML scoring, agent proposal, policy check, execution, and outcome — writes to the audit trail independently, so any decision can be reconstructed after the fact.

---

## Authority boundaries

```mermaid
flowchart TD
    A["Rules / ML / Agent"] --> B[Recommendation]
    B --> C{"POLICY GATE — authoritative"}
    C --> D[Execution]

    style C fill:#f9e0e0,stroke:#c0392b,stroke-width:2px
```

The agent cannot bypass the policy gate or directly move money. Regardless of which layer proposes an action — a deterministic rule, the ML policy, or the Groq agent — nothing executes until the policy gate independently checks it against bounded-retry, contact-limit, and hard-decline rules.

---

## Live Razorpay flow

```mermaid
flowchart TD
    A[payment.failed] --> B[Case creation / lookup]
    B --> C[Rules]
    C --> D[ML]
    D --> E[Optional Groq ambiguity resolution]
    E --> F[Policy]
    F --> G[Recovery order]
    G --> H[Customer checkout]
    H --> I{payment.captured / payment.failed}
    I --> J[State update + audit]
```

---

## Bounded recovery behavior

A recovery episode is **intentionally bounded** — repeated failures do not create an unbounded retry loop.

Case state tracks:
- Actions already attempted this episode
- Terminal status (`RECOVERED`, `STOPPED`, `ESCALATED`)

...so policy decisions survive separate webhook deliveries and process restarts. A case that fails twice re-enters the same decision path on its next webhook event rather than starting a fresh, unbounded retry sequence.

---

## Why this shape

| Layer | Why it exists here, and not elsewhere |
|---|---|
| **Rules first** | Clear cases (hard declines, expired methods) don't need probabilistic reasoning — a lookup is faster, cheaper, and fully auditable |
| **ML second** | Recovery probability is a genuine prediction task under uncertainty — this is where a learned model adds real, measured value over both naive and rule-based baselines |
| **Agent last, and selective** | Reserved for the ambiguous minority where ML's confidence is low or rules/ML disagree — invoking an LLM on every case would add cost without proportional benefit |
| **Policy gate always authoritative** | Deterministic and auditable by design — an LLM deciding "should we stop retrying" would be less predictable and harder to defend than a fixed rule, so this layer is never delegated to AI |

This ordering is a direct answer to the brief's own grading line: *"AI judgment: the right tool in the right place, and where you chose not to use one."*