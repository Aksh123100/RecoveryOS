from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recoveryos.integrations.razorpay import RazorpayTestAPIAdapter


@dataclass
class ExecutionResult:
    action: str
    status: str
    order_id: str | None = None
    detail: dict[str, Any] = field(default_factory=dict)


class RazorpayTestExecutor:
    """Bounded Test-Mode executor.

    Creating a Razorpay order is an execution artifact / recovery attempt. It
    does not itself mean that money was recovered; recovery is observed later
    from a captured payment event.
    """

    def __init__(self, adapter: RazorpayTestAPIAdapter | None = None):
        self.adapter = adapter or RazorpayTestAPIAdapter()
        self._scheduled: dict[str, dict[str, Any]] = {}

    def execute(self, case, action: str) -> ExecutionResult:
        if action == "retry_later":
            item = {
                "case_id": case.case_id,
                "amount_inr": case.amount,
                "status": "SCHEDULED",
            }
            self._scheduled[case.case_id] = item
            return ExecutionResult(action, "SCHEDULED", detail=item)

        receipt = f"recovery-{case.case_id}-{len(case.actions_attempted) + 1}"[:40]
        order = self.adapter.create_recovery_order(
            case.amount,
            receipt=receipt,
            notes={
                "recovery_case_id": str(case.case_id),
                "recovery_action": action,
                "recovery_source": "RecoveryOS",
            },
        )
        return ExecutionResult(
            action,
            "ORDER_CREATED",
            order_id=order.get("id"),
            detail={
                "receipt": receipt,
                "amount": order.get("amount"),
                "currency": order.get("currency"),
            },
        )

    def observe(self, execution: ExecutionResult) -> dict[str, Any]:
        if execution.order_id is None:
            return {"status": execution.status}

        payments = self.adapter.fetch_order_payments(execution.order_id)
        items = payments.get("items", []) or []
        captured = any(p.get("status") == "captured" for p in items)
        authorized = any(p.get("status") == "authorized" for p in items)
        return {
            "status": "RECOVERED" if captured else ("AUTHORIZED" if authorized else "PENDING"),
            "order_id": execution.order_id,
            "payment_count": len(items),
            "payments": [
                {"id": p.get("id"), "status": p.get("status"), "method": p.get("method")}
                for p in items
            ],
        }
