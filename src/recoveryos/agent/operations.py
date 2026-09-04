from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class OperatorExplanation:
    summary: str
    evidence: list[str]
    caveat: str

@dataclass(frozen=True)
class OutreachDraft:
    channel: str
    message: str
    requires_approval: bool = True

class RecoveryOpsAgent:
    """Optional LLM-facing operations layer.

    Core recovery is still Rules -> ML -> optional ambiguity Agent -> Policy Gate.
    Explanation/outreach are post-decision capabilities and cannot authorize execution.
    """
    def explain(self, case, source: str, action: str, probabilities: dict[str, float] | None = None):
        probs = probabilities or {}
        best = probs.get(action)
        detail = f"Estimated recovery probability for {action}: {best:.0%}." if best is not None else ""
        return OperatorExplanation(
            summary=f"RecoveryOS selected {action} via {source}. {detail}".strip(),
            evidence=[
                f"failure_code={case.failure_code}",
                f"historical_retry_count={case.retry_count}",
                f"merchant_recent_failure_rate={case.merchant_recent_failure_rate:.0%}",
                f"customer_previous_success_rate={case.customer_previous_success_rate:.0%}",
            ],
            caveat="This explanation is advisory; the deterministic policy gate remains authoritative."
        )

    def draft_outreach(self, case, action: str, channel: str = "sms"):
        if action == "retry_later":
            msg = "We couldn't complete your recent payment. We'll retry shortly; no action is needed right now."
        elif action == "request_alternate_method":
            msg = "We couldn't complete your recent payment. Please try another available payment method to complete your purchase."
        elif action == "retry_now":
            msg = "We couldn't complete your recent payment. We're retrying it now and will update you with the result."
        else:
            msg = "We couldn't complete your recent payment. Please contact support if you need assistance."
        return OutreachDraft(channel=channel, message=msg, requires_approval=True)
