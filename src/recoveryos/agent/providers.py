from abc import ABC,abstractmethod
import os,requests
SYSTEM_PROMPT = (
    "You are RecoveryOS ambiguity resolver. Use tools. Never execute payments or bypass policy. "
    'Return JSON with diagnosis, confidence, ranked_actions, reason.'
)
class AgentProvider(ABC):
    @abstractmethod
    def complete(self,messages,tools): raise NotImplementedError
class MockProvider(AgentProvider):
    def __init__(self, preferred="retry_later", use_tools=True):
        self.preferred=preferred; self.use_tools=use_tools; self.called=False
    def complete(self,messages,tools):
        # First turn can request tools, second turn returns a final proposal.
        if self.use_tools and not self.called:
            self.called=True
            return {
                "role":"assistant",
                "tool_calls":[
                    {"id":"call_history","type":"function","function":{"name":"get_payment_history","arguments":"{}"}},
                    {"id":"call_health","type":"function","function":{"name":"get_merchant_health","arguments":"{}"}},
                    {"id":"call_ml","type":"function","function":{"name":"predict_recovery","arguments":"{}"}}
                ]
            }
        return {"diagnosis":"mixed liquidity/degradation evidence","confidence":0.56,
                "ranked_actions":[self.preferred,"retry_now","request_alternate_method"],
                "reason":"Tool evidence is mixed; rank the strongest allowed recovery action."}
class GroqProvider(AgentProvider):
    def __init__(self,api_key=None,model=None):
        self.api_key=api_key or os.getenv("GROQ_API_KEY"); self.model=model or os.getenv("GROQ_MODEL")
        self.base_url=os.getenv("GROQ_BASE_URL","https://api.groq.com/openai/v1")
        if not self.api_key or not self.model: raise ValueError("GROQ_API_KEY and GROQ_MODEL are required")
    
    def complete(self, messages, tools):
        body = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT}
            ] + messages,
            "temperature": 0,
        }

        if tools:
            body["tools"] = tools
            body["tool_choice"] = "auto"
        else:
            # Final synthesis: explicitly prohibit tool calls.
            body["tool_choice"] = "none"

        r = requests.post(
            self.base_url + "/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=60,
        )

        if not r.ok:
            raise RuntimeError(
                f"Groq API error {r.status_code}: {r.text}"
            )

        return r.json()["choices"][0]["message"]