# Razorpay Test Mode Runbook

RecoveryOS currently validates the real Razorpay webhook -> Rules/ML decision path. The LLM agent is intentionally disabled in this live-sandbox path because our benchmark has not demonstrated incremental recovery value.

## 1. Razorpay setup

- Switch the Razorpay Dashboard to **Test Mode**.
- Generate Test API keys (`rzp_test_...`).
- Configure a webhook for `POST /webhooks/razorpay`.
- Set a webhook secret and copy the same value into `RAZORPAY_WEBHOOK_SECRET`.
- Enable the payment failure event.

Razorpay sends the signature in `X-Razorpay-Signature`. The signature is HMAC-SHA256 over the **raw request body**. Duplicate events can be identified with `x-razorpay-event-id`.

## 2. Start RecoveryOS

```bash
export RAZORPAY_WEBHOOK_SECRET='your-webhook-secret'
export RAZORPAY_KEY_ID='rzp_test_...'
export RAZORPAY_KEY_SECRET='...'
PYTHONPATH=src uvicorn recoveryos.integrations.webhook_app:app --host 0.0.0.0 --port 8000
```

Expose the HTTPS endpoint through a suitable tunnel/staging URL when configuring the Razorpay Dashboard.

## 3. Verify locally first

```bash
curl http://localhost:8000/health
```

Then post a signed `payment.failed` fixture using the same HMAC-SHA256 rule as Razorpay.

## 4. What Test Mode proves

```text
Razorpay payment.failed
        -> signature verification
        -> idempotency check
        -> RecoveryCase normalization
        -> deterministic rule (when clear)
        -> ML action selection (otherwise)
        -> policy gate
        -> audit event
```

Razorpay's Payments API is for retrieving/changing payment state; payment collection itself is done through Razorpay payment products/Checkout. Test Mode uses separate test keys and does not move real money.

Do not commit API keys or webhook secrets to Git.
