RecoveryOS

AI Revenue Recovery for Razorpay

RecoveryOS is a selective AI revenue-recovery system for failed payments. It does not blindly retry every failure. It combines deterministic rules, a learned recovery policy, a selective LLM ambiguity resolver, a hard policy gate, bounded Test-Mode execution, and event-driven observation.

The core idea

Failed payment
      |
      v
Rule diagnosis
   |       \
 clear     unclear
   |          |
 Rules        ML recovery policy
                |
          confident enough?
             /        \
           yes         no
            |           |
        ML action     Groq Agent
                         |
                    tool inspection
                         |
                  ranked proposal
                         |
                         v
                    Policy Gate
                         |
                      Execute
                         |
                      Observe
                    /         \
              captured       failed
                  |             |
              RECOVERED     bounded re-decision

The agent is not the execution authority. Any money-moving action must pass the policy gate.

What it demonstrates

Razorpay Test Mode payment.failed webhook handling

HMAC webhook signature verification

Webhook event-id idempotency

Rules -> ML -> selective Agent decision flow

Economic action ranking using expected recovery value minus intervention cost

Hard policy constraints and stopping rules

Durable SQLite case state

Recovery-order creation in Razorpay Test Mode

Recovery Checkout

payment.captured observation and case transition to RECOVERED

Audit logging of decisions, execution, and outcomes

Automated tests

Live demo

The demonstrated Test-Mode flow is:

Razorpay payment.failed
        |
        v
RecoveryOS receives webhook
        |
        v
ML selects recovery action
        |
        v
Policy Gate
        |
        v
Razorpay Test-Mode recovery order
        |
        v
Recovery Checkout
        |
        v
payment.captured
        |
        v
RecoveryOS marks case RECOVERED

A second failure on the same recovery episode can re-enter the decision path and be bounded by the recovery policy.

AI architecture

1. Rules

Clear cases are handled deterministically. Examples include known expired payment methods or insufficient-funds conditions.

2. ML recovery policy

For ambiguous cases, the model estimates recovery probabilities for the allowed actions and ranks actions economically.

The ranking objective is:

Expected net value
= P(recovery) × payment amount
  - intervention cost

The ML policy is evaluated on a controlled synthetic benchmark with customer-level splits and noisy features.

3. Selective agent

The LLM is a fallback for genuinely ambiguous ML decisions.

It can inspect tool-provided context and return a ranked proposal, but it cannot execute payments or bypass policy.

The current provider supports Groq, with a deterministic mock provider retained for tests.

4. Policy gate

The policy layer remains authoritative. It enforces constraints such as:

bounded episode retries

contact limits

duplicate-action protection

hard-decline restrictions

5. Execution and observation

Test Mode execution creates recovery orders but does not falsely treat order creation as recovered revenue.

A later Razorpay payment event closes the loop:

payment.captured -> RECOVERED
payment.failed   -> bounded re-decision / stop

Evaluation

The repository includes repeated-seed synthetic benchmarking across:

Naive retry

Strong rules

ML recovery policy

Agent proxy

Sequential oracle

Important: these are controlled synthetic benchmark results, not production Razorpay recovery rates.

On the one-step synthetic benchmark, ML achieved 56.6% recovery, versus 49.2% for strong rules and 18.3% for naive retry. ML therefore adds a 7.4 percentage-point recovery lift over the strong-rule baseline and a 38.3 percentage-point lift over naive retry. The evaluator-only oracle reached 66.4%.

These figures are controlled synthetic benchmark results, not production Razorpay recovery rates. The agent benchmark is reported separately because it is an ambiguity-resolution mechanism rather than a claim of incremental recovery uplift.

What broke and how it was fixed

Razorpay webhook path

The initial webhook parser expected the wrong payload nesting. The live Razorpay event structure was corrected to read the payment entity from payload.payment.entity.

Webhook URL mismatch

A Cloudflare Quick Tunnel initially received Razorpay traffic on /, producing 404. The webhook target was corrected to /webhooks/razorpay.

Persistent test state

Once durable SQLite state was introduced, fixed test IDs survived between test runs. The stale local database was cleared during integration testing, while the persistent state implementation itself was retained.

Recovery observation

A successful Test-Mode recovery payment produced:

payment.captured
-> CASE_UPDATE
-> status=RECOVERED

This verified the event-driven observation path end-to-end.

Agent path

The system supports a real Groq provider and a mock provider. The real LLM is intentionally selective and is not granted execution authority.

Test Mode evidence

The live Test-Mode demonstration covered:

payment.failed
-> request_alternate_method
-> recovery order created
-> Recovery Checkout
-> payment.captured
-> RECOVERED

The system also demonstrated a failed recovery attempt returning to the decision layer and selecting retry_later.

Repository structure

RecoveryOS/
├── benchmark/
├── src/
│   └── recoveryos/
│       ├── agent/
│       ├── audit/
│       ├── domain/
│       ├── engine/
│       ├── evaluation/
│       └── integrations/
├── tests/
├── README.md
├── ARCHITECTURE.md
├── RAZORPAY_TESTMODE_RUNBOOK.md
├── requirements.txt
├── pyproject.toml
├── .env.example
└── .gitignore

Run locally

1. Install

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

2. Configure environment

Create .env from .env.example.

Never commit .env.

Typical local settings:

RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...
RAZORPAY_EXECUTION_ENABLED=true

For the optional real Groq provider:

RECOVERYOS_AGENT_PROVIDER=groq
GROQ_API_KEY=...
GROQ_MODEL=llama-3.3-70b-versatile

3. Run tests

$env:PYTHONPATH="src"
pytest -q

4. Start the service

$env:PYTHONPATH="src"
python -m uvicorn recoveryos.integrations.webhook_app:app --reload --port 8000

Useful endpoints:

GET /health
GET /dashboard
POST /webhooks/razorpay

Safety / authority model

The architecture deliberately separates:

AI suggestion
    |
    v
Policy authority
    |
    v
Money-moving execution

The LLM cannot directly execute a payment, change policy constraints, or bypass the gate.

Demo video

5-minute pitch video: add final unlisted/public link here

Architecture

See ARCHITECTURE.md.

Status

RecoveryOS is a Test-Mode prototype demonstrating the complete bounded recovery loop. It is not a production payment-recovery service.