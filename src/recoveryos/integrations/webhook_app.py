from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from html import escape

from .razorpay import RazorpayTestAPIAdapter, RazorpayWebhookVerifier
from recoveryos.audit.logger import AuditLogger
from recoveryos.domain.models import RecoveryCase
from recoveryos.engine.executor import RazorpayTestExecutor
from recoveryos.engine.policy import RecoveryPolicy
from recoveryos.engine.razorpay_workflow import RazorpayRecoveryWorkflow
from recoveryos.engine.state import CaseStore
from recoveryos.evaluation.ml_policy import RecoveryMLPolicy
from recoveryos.evaluation.world import generate_cases
from recoveryos.agent.providers import GroqProvider, MockProvider
from recoveryos.agent.tools import AgentToolbox, SelectiveRecoveryAgent


logger = logging.getLogger("uvicorn.error")

load_dotenv()

app = FastAPI(
    title="RecoveryOS Razorpay Test Adapter",
    version="0.3.0",
)

_secret_default = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

_state = CaseStore(
    os.getenv(
        "RECOVERYOS_STATE_DB",
        "recoveryos_state.sqlite3",
    )
)

_model = RecoveryMLPolicy().fit(
    generate_cases(10000, 1234)
)

_audit = AuditLogger()


# ---------------------------------------------------------------------------
# Agent configuration
# ---------------------------------------------------------------------------

provider_name = os.getenv(
    "RECOVERYOS_AGENT_PROVIDER",
    "mock",
).lower()

if provider_name == "groq":
    try:
        _agent_provider = GroqProvider()
    except ValueError:
        logger.warning(
            "Groq agent requested but credentials/model missing; "
            "falling back to mock provider"
        )
        _agent_provider = MockProvider(use_tools=True)
else:
    _agent_provider = MockProvider(use_tools=True)

_agent = SelectiveRecoveryAgent(
    _agent_provider,
    AgentToolbox(_model),
)


# ---------------------------------------------------------------------------
# Test-mode execution configuration
# ---------------------------------------------------------------------------

_execution_enabled = (
    os.getenv(
        "RAZORPAY_EXECUTION_ENABLED",
        "false",
    ).lower()
    == "true"
)

_executor = None

if _execution_enabled:
    try:
        _executor = RazorpayTestExecutor(
            RazorpayTestAPIAdapter()
        )
    except ValueError as exc:
        logger.warning(
            "Test execution disabled: %s",
            exc,
        )


_policy = RecoveryPolicy(
    max_episode_retries=2,
    max_contacts=1,
)

_workflow = RazorpayRecoveryWorkflow(
    _model,
    _policy,
    _audit,
    agent=_agent,
    executor=_executor,
)


# ---------------------------------------------------------------------------
# Case creation / lookup
# ---------------------------------------------------------------------------

def _case_from_payment(
    payment: dict,
    existing: RecoveryCase | None = None,
) -> RecoveryCase:
    notes = payment.get("notes") or {}

    amount = (
        float(
            payment.get("amount")
            or (
                existing.amount * 100
                if existing
                else 0
            )
        )
        / 100.0
    )

    raw_code = (
        payment.get("error_code")
        or payment.get("error_reason")
        or "UNKNOWN"
    )

    # These are the synthetic benchmark categories the model knows.
    # Real Razorpay codes that do not belong to this vocabulary are
    # normalized to UNKNOWN rather than being treated as known categories.
    known_codes = {
        "TIMEOUT",
        "DECLINED",
        "INSUFFICIENT_FUNDS_CODE",
        "EXPIRED_CODE",
        "NETWORK_ERROR",
        "NO_ATTEMPT",
        "HARD_DECLINE",
        "HARD_DECLINE_CODE",
    }

    code = (
        raw_code
        if raw_code in known_codes
        else "UNKNOWN"
    )

    if existing:
        existing.amount = amount or existing.amount
        existing.failure_code = code
        return existing

    return RecoveryCase(
        case_id=str(
            payment.get("id")
            or payment.get("order_id")
            or "unknown"
        ),
        amount=amount,
        failure_code=code,
        customer_previous_success_rate=float(
            notes.get(
                "customer_success_rate",
                0.80,
            )
        ),
        merchant_recent_failure_rate=float(
            notes.get(
                "merchant_failure_rate",
                0.10,
            )
        ),
        days_since_last_success=float(
            notes.get(
                "days_since_last_success",
                3,
            )
        ),
        retry_count=int(
            notes.get(
                "historical_retry_count",
                0,
            )
        ),
        time_since_failure=float(
            notes.get(
                "time_since_failure",
                1,
            )
        ),
        device_type=str(
            notes.get(
                "device_type",
                "unknown",
            )
        ),
        time_of_day=str(
            notes.get(
                "time_of_day",
                "unknown",
            )
        ),
    )


def _find_case(
    payment: dict,
) -> RecoveryCase | None:
    payment_id = payment.get("id")
    order_id = payment.get("order_id")

    if payment_id:
        case = _state.get_case(
            str(payment_id)
        )

        if case:
            return case

    mapped = _state.case_id_for_order(
        order_id
    )

    return (
        _state.get_case(mapped)
        if mapped
        else None
    )


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {
        "ok": True,
        "mode": "razorpay_test",
        "decision_engine": (
            "rules_then_ml_then_agent_on_ambiguity"
        ),
        "agent_provider": provider_name,
        "agent_execution_authority": False,
        "execution_enabled": (
            _executor is not None
        ),
        "state_store": str(
            Path(_state.path).resolve()
        ),
    }


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get(
    "/dashboard",
    response_class=HTMLResponse,
)
def dashboard():
    cases = _state.list_cases(
        limit=25
    )

    rows = []

    for c in cases:
        order_id = _state.order_id_for_case(
            c["case_id"]
        )

        action_html = escape(
            c["last_action"] or "-"
        )

        if (
            order_id
            and c["status"]
            not in {
                "RECOVERED",
                "STOPPED",
                "ESCALATED",
            }
        ):
            action_html += (
                f" <a href='/dashboard/recovery/"
                f"{escape(c['case_id'])}'>"
                "Open recovery checkout"
                "</a>"
            )

        rows.append(
            f"<tr>"
            f"<td>{escape(c['case_id'])}</td>"
            f"<td>₹{c['amount']:.2f}</td>"
            f"<td>{escape(c['failure_code'])}</td>"
            f"<td>{escape(c['status'])}</td>"
            f"<td>{action_html}</td>"
            f"<td>{c['episode_retry_count']}</td>"
            f"<td>{'YES' if c['agent_invoked'] else 'NO'}</td>"
            f"</tr>"
        )

    body = "".join(rows)

    if not body:
        body = (
            '<tr>'
            '<td colspan="7">No cases yet.</td>'
            '</tr>'
        )

    return HTMLResponse(
        f"""
<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width,initial-scale=1"
    >
    <meta
        http-equiv="refresh"
        content="5"
    >

    <title>RecoveryOS Dashboard</title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 32px;
            background: #f7f7f8;
            color: #171717;
        }}

        .card {{
            background: white;
            padding: 20px;
            border-radius: 12px;
            margin-bottom: 18px;
            box-shadow: 0 1px 6px #ddd;
        }}

        h1 {{
            margin-top: 0;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th,
        td {{
            padding: 10px;
            border-bottom: 1px solid #eee;
            text-align: left;
        }}

        a {{
            margin-left: 10px;
        }}

        code {{
            background: #eee;
            padding: 3px 6px;
            border-radius: 4px;
        }}
    </style>
</head>

<body>

<div class="card">
    <h1>RecoveryOS</h1>

    <p>
        Selective AI revenue recovery · Test Mode ·
        refreshes every 5s
    </p>

    <p>
        <b>Decision:</b>
        Rules → ML → Agent on ambiguity
        → Policy Gate → Execute → Observe
    </p>

    <p>
        <b>Execution:</b>
        {"ENABLED" if _executor is not None else "DISABLED"}
    </p>
</div>

<div class="card">
    <h2>Recent cases</h2>

    <table>
        <tr>
            <th>Case</th>
            <th>Amount</th>
            <th>Failure</th>
            <th>Status</th>
            <th>Last action</th>
            <th>Episode retries</th>
            <th>Agent</th>
        </tr>

        {body}

    </table>
</div>

</body>
</html>
"""
    )


# ---------------------------------------------------------------------------
# Recovery checkout
# ---------------------------------------------------------------------------

@app.get(
    "/dashboard/recovery/{case_id}",
    response_class=HTMLResponse,
)
def recovery_checkout(
    case_id: str,
):
    case = _state.get_case(
        case_id
    )

    if not case:
        raise HTTPException(
            404,
            "Recovery case not found",
        )

    order_id = _state.order_id_for_case(
        case_id
    )

    if not order_id:
        raise HTTPException(
            404,
            "No recovery order exists for this case",
        )

    key_id = os.getenv(
        "RAZORPAY_KEY_ID",
        "",
    )

    if not key_id.startswith(
        "rzp_test_"
    ):
        raise HTTPException(
            503,
            "Razorpay Test-Mode key is not configured",
        )

    if case.status in {
        "RECOVERED",
        "STOPPED",
        "ESCALATED",
    }:
        raise HTTPException(
            409,
            f"Case is already terminal: {case.status}",
        )

    amount_paise = int(
        round(case.amount * 100)
    )

    last_action = (
        case.actions_attempted[-1]
        if case.actions_attempted
        else "-"
    )

    return HTMLResponse(
        f"""
<!doctype html>
<html>

<head>
    <meta charset="utf-8">

    <meta
        name="viewport"
        content="width=device-width,initial-scale=1"
    >

    <title>
        RecoveryOS - Test Checkout
    </title>

    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 40px;
            background: #f7f7f8;
            color: #171717;
        }}

        .card {{
            max-width: 600px;
            background: white;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px #ddd;
        }}

        button {{
            padding: 12px 20px;
            border: 0;
            border-radius: 8px;
            cursor: pointer;
            font-size: 16px;
        }}
    </style>
</head>

<body>

<div class="card">

    <h1>Recovery Checkout</h1>

    <p>
        <b>Case:</b>
        {escape(case.case_id)}
        <br>

        <b>Amount:</b>
        ₹{case.amount:.2f}
        <br>

        <b>Recovery Order:</b>
        {escape(order_id)}
        <br>

        <b>Action:</b>
        {escape(last_action)}
    </p>

    <button id="rzp-button">
        Pay ₹{case.amount:.2f}
    </button>

    <p>
        <a href="/dashboard">
            Back to dashboard
        </a>
    </p>

</div>

<script src="https://checkout.razorpay.com/v1/checkout.js"></script>

<script>
const options = {{
    key: {json.dumps(key_id)},
    amount: {amount_paise},
    currency: "INR",
    name: "RecoveryOS",
    description: "Revenue Recovery - Test Mode",
    order_id: {json.dumps(order_id)},

    handler: function(response) {{
        document.body.innerHTML = `
            <div class="card">

                <h1>
                    Payment Submitted
                </h1>

                <p>
                    Payment ID:
                    ${{response.razorpay_payment_id}}
                </p>

                <p>
                    RecoveryOS will update automatically
                    when the Razorpay webhook arrives.
                </p>

                <p>
                    <a href="/dashboard">
                        Back to dashboard
                    </a>
                </p>

            </div>
        `;
    }}
}};

const rzp = new Razorpay(options);

document.getElementById(
    "rzp-button"
).onclick = function(e) {{
    e.preventDefault();
    rzp.open();
}};
</script>

</body>
</html>
"""
    )


# ---------------------------------------------------------------------------
# Razorpay webhook
# ---------------------------------------------------------------------------

@app.post("/webhooks/razorpay")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(
        default=None
    ),
    x_razorpay_event_id: str | None = Header(
        default=None
    ),
):
    raw = await request.body()

    # 1. Signature validation
    if not x_razorpay_signature:
        raise HTTPException(
            400,
            "Missing X-Razorpay-Signature",
        )

    try:
        ok = RazorpayWebhookVerifier(
            _secret_default or None
        ).verify(
            raw,
            x_razorpay_signature,
        )
    except ValueError as exc:
        raise HTTPException(
            500,
            str(exc),
        )

    if not ok:
        raise HTTPException(
            401,
            "Invalid webhook signature",
        )

    # 2. Event-id idempotency
    if not x_razorpay_event_id:
        raise HTTPException(
            400,
            "Missing x-razorpay-event-id",
        )

    if _state.has_event(
        x_razorpay_event_id
    ):
        return {
            "ok": True,
            "duplicate": True,
            "event_id": x_razorpay_event_id,
        }

    # 3. Parse JSON
    try:
        payload = json.loads(
            raw.decode("utf-8")
        )
    except json.JSONDecodeError:
        raise HTTPException(
            400,
            "Invalid JSON",
        )

    event = payload.get(
        "event"
    )

    logger.info(
        "[WEBHOOK] event=%s event_id=%s",
        event,
        x_razorpay_event_id,
    )

    # Razorpay standard structure:
    # payload.payment.entity
    #
    # The fallback also supports the older synthetic
    # test payload shape:
    # payload[event].entity
    entity = (
        payload.get("payload", {})
        .get("payment", {})
        .get("entity", {})
    )

    if not entity:
        entity = (
            payload.get("payload", {})
            .get(event or "", {})
            .get("entity", {})
        )

    # -----------------------------------------------------------------------
    # payment.failed
    # -----------------------------------------------------------------------

    if event == "payment.failed":
        existing = _find_case(
            entity
        )

        case = _case_from_payment(
            entity,
            existing,
        )

        if existing:
            # Terminal cases cannot be reopened.
            if case.status in {
                "RECOVERED",
                "STOPPED",
                "ESCALATED",
            }:
                _state.mark_event(
                    x_razorpay_event_id,
                    event,
                )

                return {
                    "ok": True,
                    "accepted": True,
                    "event": event,
                    "ignored_terminal_case": True,
                }

            case.outcome_history.append(
                {
                    "event": "payment.failed",
                    "payment_id": entity.get("id"),
                }
            )

            if case.actions_attempted:
                last_action = (
                    case.actions_attempted[-1]
                )

                if last_action in {
                    "retry_now",
                    "retry_later",
                }:
                    case.episode_retry_count += 1

        # 4. Rules → ML → optional Agent → Policy → Execute → Observe
        result = _workflow.handle_case(
            case
        )

        # 5. Persist case state
        _state.put_case(
            case
        )

        # 6. Persist recovery-order → case mapping
        if getattr(
            result.execution,
            "order_id",
            None,
        ):
            _state.map_order(
                result.execution.order_id,
                case.case_id,
            )

        # 7. Persist processed webhook event
        _state.mark_event(
            x_razorpay_event_id,
            event,
        )

        logger.info(
            "[RECOVERYOS] payment=%s case=%s "
            "amount=%s failure_code=%s "
            "source=%s action=%s blocked=%s "
            "execution=%s order=%s",
            entity.get("id"),
            case.case_id,
            case.amount,
            case.failure_code,
            result.source,
            result.action,
            result.blocked_reason,
            getattr(
                result.execution,
                "status",
                None,
            ),
            getattr(
                result.execution,
                "order_id",
                None,
            ),
        )

        return {
            "ok": True,
            "accepted": True,
            "event": event,
            "event_id": x_razorpay_event_id,
            "payment_id": entity.get("id"),
            "case_id": case.case_id,
            "amount_inr": case.amount,
            "failure_code": case.failure_code,
            "decision_source": result.source,
            "selected_action": result.action,
            "policy_block": result.blocked_reason,
            "execution_status": getattr(
                result.execution,
                "status",
                None,
            ),
            "recovery_order_id": getattr(
                result.execution,
                "order_id",
                None,
            ),
            "observation": result.observation,
        }

    # -----------------------------------------------------------------------
    # payment.captured / payment.authorized
    # -----------------------------------------------------------------------

    if event in {
        "payment.captured",
        "payment.authorized",
    }:
        case = _find_case(
            entity
        )
        logger.info(
        "[RECOVERYOS] OBSERVATION event=%s payment=%s order=%s",
        event,
        entity.get("id"),
        entity.get("order_id"),
    )    

        if case:
            status = (
                "RECOVERED"
                if event == "payment.captured"
                else "AUTHORIZED"
            )

            case.status = status
            logger.info(
                "[RECOVERYOS] CASE_UPDATE case=%s status=%s",
                case.case_id,
                case.status,
            )

            case.outcome_history.append(
                {
                    "event": event,
                    "payment_id": entity.get("id"),
                }
            )

            _state.put_case(
                case
            )

            _audit.record(
                "payment_observed",
                event=event,
                payment_id=entity.get("id"),
                order_id=entity.get("order_id"),
                case_id=case.case_id,
            )

        _state.mark_event(
            x_razorpay_event_id,
            event,
        )

        return {
            "ok": True,
            "accepted": True,
            "event": event,
            "payment_id": entity.get("id"),
            "observed": True,
            "case_id": (
                case.case_id
                if case
                else None
            ),
        }

    # -----------------------------------------------------------------------
    # Other events
    # -----------------------------------------------------------------------

    _state.mark_event(
        x_razorpay_event_id,
        event,
    )

    return {
        "ok": True,
        "accepted": True,
        "ignored": True,
        "event": event,
    }