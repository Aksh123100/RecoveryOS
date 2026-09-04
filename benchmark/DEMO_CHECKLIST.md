# RecoveryOS Demo Checklist

1. Start FastAPI and Cloudflare tunnel.
2. Confirm `GET /health` returns `ok: true`.
3. Confirm `GET /dashboard` loads.
4. Create a Razorpay Test Mode payment and force a failure.
5. Confirm `POST /webhooks/razorpay` returns 200 and logs `[RECOVERYOS]`.
6. Open `/dashboard` and show the case, selected action, policy state, and retry count.
7. For an executed recovery attempt, show the created Test-Mode recovery order.
8. Complete a Test-Mode recovery payment when applicable.
9. Show the later `payment.captured` event changing the case to `RECOVERED`.
10. Restart FastAPI and verify the case/event state remains in SQLite.
