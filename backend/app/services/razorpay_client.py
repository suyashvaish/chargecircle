"""Payment provider access: real Razorpay REST API, plus a development-only mock with the same interface."""
import hashlib
import hmac
import uuid
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.config import settings

_transport: Optional[httpx.BaseTransport] = None  # tests inject httpx.MockTransport here


class ProviderError(Exception):
    """The payment provider rejected or failed a request."""


class ProviderNotConfigured(ProviderError):
    pass


def compute_signature(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()


def verify_checkout_signature(order_id: str, payment_id: str, signature: str, secret: str) -> bool:
    expected = compute_signature(secret, f"{order_id}|{payment_id}".encode("utf-8"))
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str, secret: str) -> bool:
    return hmac.compare_digest(compute_signature(secret, raw_body), signature or "")


class RazorpayProvider:
    is_mock = False

    def __init__(self, key_id: str, key_secret: str, base_url: str):
        self.key_id, self.key_secret, self.base = key_id, key_secret, base_url.rstrip("/")

    @property
    def checkout_secret(self) -> str:
        return self.key_secret

    def _request(self, method: str, path: str, payload: Optional[dict] = None) -> Dict[str, Any]:
        try:
            with httpx.Client(timeout=15.0, transport=_transport, auth=(self.key_id, self.key_secret)) as client:
                resp = client.request(method, f"{self.base}{path}", json=payload)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Payment provider unreachable ({type(exc).__name__})") from exc
        if resp.status_code >= 400:
            try:
                desc = resp.json().get("error", {}).get("description", "")
            except Exception:
                desc = ""
            raise ProviderError(f"Payment provider error {resp.status_code}: {desc[:200]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise ProviderError("Payment provider returned an unreadable response") from exc

    def create_order(self, amount_paise: int, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
        return self._request("POST", "/orders", {"amount": amount_paise, "currency": "INR",
                                                 "receipt": receipt[:40], "notes": notes})

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        return self._request("GET", f"/payments/{payment_id}")

    def capture_payment(self, payment_id: str, amount_paise: int) -> Dict[str, Any]:
        return self._request("POST", f"/payments/{payment_id}/capture", {"amount": amount_paise, "currency": "INR"})

    def refund_payment(self, payment_id: str, amount_paise: int, notes: Dict[str, str]) -> Dict[str, Any]:
        return self._request("POST", f"/payments/{payment_id}/refund", {"amount": amount_paise, "notes": notes})


class MockProvider:
    """Local development stand-in. Signatures are still verified with HMAC; nothing is auto-approved."""
    is_mock = True

    @property
    def checkout_secret(self) -> str:
        return hashlib.sha256(("mock-provider:" + settings.SECRET_KEY).encode()).hexdigest()

    def create_order(self, amount_paise: int, receipt: str, notes: Dict[str, str]) -> Dict[str, Any]:
        return {"id": f"order_mock_{uuid.uuid4().hex[:14]}", "amount": amount_paise, "currency": "INR", "status": "created"}

    def simulate_payment(self, order_id: str) -> Tuple[str, str]:
        payment_id = f"pay_mock_{uuid.uuid4().hex[:14]}"
        return payment_id, compute_signature(self.checkout_secret, f"{order_id}|{payment_id}".encode())

    def fetch_payment(self, payment_id: str) -> Dict[str, Any]:
        raise ProviderError("not available in mock mode")

    def capture_payment(self, payment_id: str, amount_paise: int) -> Dict[str, Any]:
        return {"id": payment_id, "status": "captured"}

    def refund_payment(self, payment_id: str, amount_paise: int, notes: Dict[str, str]) -> Dict[str, Any]:
        return {"id": f"rfnd_mock_{uuid.uuid4().hex[:12]}", "amount": amount_paise, "status": "processed"}


def get_provider():
    if settings.PAYMENT_MODE == "razorpay":
        if not (settings.RAZORPAY_KEY_ID and settings.RAZORPAY_KEY_SECRET):
            raise ProviderNotConfigured("Razorpay credentials are not configured (RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET)")
        return RazorpayProvider(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET, settings.RAZORPAY_API_BASE)
    if settings.mock_payments_allowed:
        return MockProvider()
    raise ProviderNotConfigured("No payment provider is available (set PAYMENT_MODE=razorpay with credentials)")
