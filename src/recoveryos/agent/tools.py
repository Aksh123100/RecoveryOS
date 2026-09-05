import json
class AgentToolbox:
    def __init__(self,ml_model): self.ml_model=ml_model
    def get_payment_history(self,case):
        return {"failure_code":case.failure_code,"historical_retry_count":case.retry_count,
                "episode_retry_count":case.episode_retry_count,"recent_outcomes":case.outcome_history[-3:],
                "customer_success_rate":case.customer_previous_success_rate}
    def get_merchant_health(self,case):
        return {"recent_failure_rate":case.merchant_recent_failure_rate,
                "possible_degradation":case.merchant_recent_failure_rate>=.20}
    def predict_recovery(self,case):
        return self.ml_model.predict_probabilities(case.to_feature_case())
    def schemas(self):
        blank={"type":"object","properties":{},"additionalProperties":False}
        return [
            {"type":"function","function":{"name":"get_payment_history","description":"Inspect case retry and outcome history","parameters":blank}},
            {"type":"function","function":{"name":"get_merchant_health","description":"Inspect merchant recent failure health","parameters":blank}},
            {"type":"function","function":{"name":"predict_recovery","description":"Get ML P(recovery|action)","parameters":blank}}
        ]
class SelectiveRecoveryAgent:
    def __init__(self, provider, toolbox, max_tool_rounds=3):
        self.provider = provider
        self.toolbox = toolbox
        self.max_tool_rounds = max_tool_rounds

    def _parse_final(self, result):
        if not isinstance(result, dict):
            return None

        # Some providers may already return structured JSON.
        if "ranked_actions" in result:
            return result

        content = result.get("content")

        if not content:
            return None

        if isinstance(content, dict):
            return content

        # Normal JSON response.
        try:
            parsed = json.loads(content)

            if isinstance(parsed, dict) and "ranked_actions" in parsed:
                return parsed

        except (TypeError, json.JSONDecodeError):
            pass

        # Handle accidental ```json ... ``` wrapping.
        if isinstance(content, str):
            cleaned = content.strip()

            if cleaned.startswith("```"):
                lines = cleaned.splitlines()

                if lines and lines[0].startswith("```"):
                    lines = lines[1:]

                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]

                cleaned = "\n".join(lines).strip()

                try:
                    parsed = json.loads(cleaned)

                    if isinstance(parsed, dict) and "ranked_actions" in parsed:
                        return parsed

                except json.JSONDecodeError:
                    pass

        return None

    def _fallback(self, case):
        """
        Safe deterministic fallback.

        The agent never executes payments.
        If the LLM cannot produce a valid recommendation,
        reuse the ML policy ranking.
        """
        allowed = [
            "retry_now",
            "retry_later",
            "request_alternate_method",
        ]

        probs = self.toolbox.predict_recovery(case)

        costs = {
            "retry_now": 0.20,
            "retry_later": 0.20,
            "request_alternate_method": 1.50,
        }

        ranked = sorted(
            allowed,
            key=lambda action: (
                probs[action] * case.amount - costs[action]
            ),
            reverse=True,
        )

        return {
            "diagnosis": (
                "Agent investigation did not converge; "
                "falling back to ML ranking."
            ),
            "confidence": 0.0,
            "ranked_actions": ranked,
            "reason": (
                "The bounded agent investigation exhausted its "
                "tool budget or returned an invalid final response."
            ),
            "fallback": True,
        }

    def investigate(self, case):
        messages = [{
            "role": "user",
            "content": (
                f"Case ₹{case.amount:.2f}; "
                f"failure={case.failure_code}; "
                f"historical_retry_count={case.retry_count}; "
                f"episode_retry_count={case.episode_retry_count}; "
                f"merchant_failure_rate={case.merchant_recent_failure_rate:.2f}; "
                f"customer_success_rate={case.customer_previous_success_rate:.2f}. "
                "Investigate this ambiguous recovery case using the available "
                "tools. Then return a final JSON object with exactly these "
                "fields: diagnosis, confidence, ranked_actions, reason."
            ),
        }]

        for round_number in range(self.max_tool_rounds):

            result = self.provider.complete(
                messages,
                self.toolbox.schemas(),
            )

            # The model may decide it already has enough information.
            parsed = self._parse_final(result)

            if parsed is not None:
                return parsed

            calls = (
                result.get("tool_calls", [])
                if isinstance(result, dict)
                else []
            )

            # The model did not return a final answer and did not ask
            # for tools. Treat that as a controlled agent failure.
            if not calls:
                return self._fallback(case)

            # Preserve the assistant tool-call message.
            messages.append(result)

            # Execute only the explicitly exposed investigation tools.
            for call in calls:
                name = call["function"]["name"]
                args = call["function"].get("arguments", "{}")

                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}

                if not hasattr(self.toolbox, name):
                    continue

                out = getattr(self.toolbox, name)(case)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "name": name,
                    "content": json.dumps(out),
                })

            # We have reached the investigation budget.
            # Ask the model for one final synthesis with tools disabled.
            if round_number == self.max_tool_rounds - 1:

                messages.append({
                    "role": "user",
                    "content": (
                        "The investigation budget is exhausted. "
                        "Do not request any more tools. "
                        "Synthesize the evidence already collected and "
                        "return ONLY valid JSON with exactly these fields: "
                        "diagnosis, confidence, ranked_actions, reason."
                    ),
                })

                final_result = self.provider.complete(messages, [])

                parsed = self._parse_final(final_result)

                if parsed is not None:
                    return parsed

                return self._fallback(case)

        return self._fallback(case)