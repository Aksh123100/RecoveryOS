import hashlib, hmac, json
from fastapi.testclient import TestClient

from recoveryos.integrations import webhook_app


def sign(raw):
    return hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()


def test_stateful_duplicate_and_observation(monkeypatch, tmp_path):
    monkeypatch.setattr(webhook_app, "_state", webhook_app.CaseStore(str(tmp_path / "state.sqlite3")))
    webhook_app._secret_default = "test-secret"

    client = TestClient(webhook_app.app)
    failed = {
        "event": "payment.failed",
        "payload": {"payment": {"entity": {
            "id": "pay_state_1", "order_id": "order_orig", "amount": 10000,
            "error_code": "EXPIRED_CODE", "notes": {}
        }}}
    }
    raw = json.dumps(failed, separators=(",", ":")).encode()
    r = client.post("/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sign(raw), "x-razorpay-event-id": "evt_state_1"})
    assert r.status_code == 200
    assert r.json()["selected_action"] == "request_alternate_method"

    dup = client.post("/webhooks/razorpay", content=raw, headers={"X-Razorpay-Signature": sign(raw), "x-razorpay-event-id": "evt_state_1"})
    assert dup.json()["duplicate"] is True
