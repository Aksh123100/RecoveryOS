RecoveryOS Architecture

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

    C --> U[Audit Trail]
    D --> U
    F --> U
    I --> U
    L --> U
    O --> U
    R --> U

Authority boundaries

Rules / ML / Agent
       |
       v
 recommendation
       |
       v
  POLICY GATE  <--- authoritative
       |
       v
   EXECUTION

The agent cannot bypass the policy gate or directly move money.

Live Razorpay flow

payment.failed
    |
    v
case creation / lookup
    |
    v
rules
    |
    v
ML
    |
    v
optional Groq ambiguity resolution
    |
    v
policy
    |
    v
recovery order
    |
    v
customer checkout
    |
    v
payment.captured / payment.failed
    |
    v
state update + audit

Bounded recovery behavior

A recovery episode is intentionally bounded.

Repeated failures do not create an unbounded retry loop. Case state tracks attempted actions and terminal status so policy decisions survive separate webhook deliveries and process restarts.