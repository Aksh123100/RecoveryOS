# RecoveryOS

Selective AI revenue-recovery engine for failed payments.

Flow:
FAILED PAYMENT -> deterministic rules -> ML scoring -> selective AI ambiguity resolver -> policy gate -> bounded execution -> observe -> re-score/stop -> audit.

The LLM never executes financial actions and cannot bypass the deterministic policy gate.

Offline evaluation uses controlled synthetic data. It is not a claim about real Razorpay recovery rates.

The ML benchmark is a real scikit-learn model trained on generated historical outcomes and evaluated on separate cases. Repeated-seed evaluation uses stable counterfactual outcomes.

`retry_count` = historical retries before RecoveryOS.
`episode_retry_count` = retries performed by RecoveryOS in the current episode.
These fields are intentionally separate.

Benchmark intervention costs are assumptions, not Razorpay fees:
retry_now ₹0.20, retry_later ₹0.20, request_alternate_method ₹1.50.

Run:
pip install -r requirements.txt
pytest -q
PYTHONPATH=src python -m recoveryos.evaluation.run_repeated

Agent provider:
RECOVERYOS_AGENT_PROVIDER=mock for tests.
For an OpenAI-compatible provider such as Groq, set GROQ_API_KEY and GROQ_MODEL.


## Razorpay Test Mode integration

The integration layer receives Razorpay payment webhooks, validates the HMAC-SHA256 signature using the raw request body, deduplicates events using the Razorpay event ID, and normalizes payment events for the RecoveryOS engine. Razorpay documents `payment.failed`, `payment.authorized`, and `payment.captured` events and recommends webhook signature validation plus idempotent handling.

Run locally:

```bash
pip install -r requirements.txt
export RAZORPAY_WEBHOOK_SECRET=...
PYTHONPATH=src uvicorn recoveryos.integrations.webhook_app:app --reload --port 8000
```

The Test API adapter requires an `rzp_test_` key pair and supports fetching a payment, fetching an order's payments, and creating a new Test-Mode recovery order. Creating an order does not itself charge a customer; payment collection still uses Razorpay Checkout. RecoveryOS persists case/order state in SQLite so later webhook events can re-enter the same bounded recovery episode.


## Current live-sandbox decision policy
The Razorpay Test Mode path uses deterministic rules first, then the trained ML policy, with the agent invoked only for ambiguous cases. The deterministic policy gate remains authoritative. Agent provider selection is controlled by RECOVERYOS_AGENT_PROVIDER (mock by default; groq when configured).
