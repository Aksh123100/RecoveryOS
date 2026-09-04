from __future__ import annotations
import hashlib, hmac, os
from typing import Any
import requests

class RazorpayWebhookVerifier:
    def __init__(self, secret: str | None = None):
        self.secret = secret or os.getenv('RAZORPAY_WEBHOOK_SECRET')
        if not self.secret:
            raise ValueError('RAZORPAY_WEBHOOK_SECRET is required')
    def verify(self, raw_body: bytes, signature: str) -> bool:
        expected = hmac.new(self.secret.encode(), raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

class RazorpayTestAPIAdapter:
    """Small Test-Mode adapter for payment lookup and recovery-order creation."""
    def __init__(self, key_id: str | None = None, key_secret: str | None = None):
        self.key_id = key_id or os.getenv('RAZORPAY_KEY_ID')
        self.key_secret = key_secret or os.getenv('RAZORPAY_KEY_SECRET')
        self.base_url = os.getenv('RAZORPAY_BASE_URL', 'https://api.razorpay.com/v1')
        if not self.key_id or not self.key_secret:
            raise ValueError('RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET are required')
        if not self.key_id.startswith('rzp_test_'):
            raise ValueError('This adapter is intentionally Test-Mode-only; expected rzp_test_ key.')

    def _request(self, method: str, path: str, **kwargs):
        r = requests.request(method, self.base_url + path, auth=(self.key_id, self.key_secret), timeout=20, **kwargs)
        r.raise_for_status()
        return r.json()

    def fetch_payment(self, payment_id: str) -> dict[str, Any]:
        return self._request('GET', f'/payments/{payment_id}')

    def fetch_order_payments(self, order_id: str) -> dict[str, Any]:
        return self._request('GET', f'/orders/{order_id}/payments')

    def create_recovery_order(self, amount_inr: float, receipt: str, notes: dict[str, str] | None = None) -> dict[str, Any]:
        # This creates a new Test-Mode order; payment collection still happens through Checkout.
        payload = {
            'amount': int(round(amount_inr * 100)),
            'currency': 'INR',
            'receipt': receipt,
            'notes': notes or {},
        }
        return self._request('POST', '/orders', json=payload)
