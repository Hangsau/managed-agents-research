"""LLM client with fallback chain."""
import json, urllib.request
from .config import API_URL, API_KEY, MODEL, MODEL_FALLBACKS


def _call_single_model(model: str, messages: list[dict], max_tokens: int, tools: list[dict] | None = None):
    """Single model call. Returns (response_dict, error)."""
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }
    if tools:
        payload["tools"] = tools
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "ManagedAgents-Harness/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            if "error" in result:
                return None, result["error"]
            if "choices" in result and result["choices"]:
                return result, None
            return None, "No choices in response"
    except Exception as e:
        return None, str(e)


def call_llm(messages: list[dict], max_tokens: int = 1000, tools: list[dict] | None = None) -> dict | None:
    """Call LLM with fallback chain. Returns raw response dict or None on total failure."""
    result, err = _call_single_model(MODEL, messages, max_tokens, tools)
    if result is not None:
        return result
    print(f"[LLM] Primary model {MODEL} failed: {err}")

    fallback = MODEL_FALLBACKS.get(MODEL)
    while fallback:
        result, err = _call_single_model(fallback, messages, max_tokens, tools)
        if result is not None:
            print(f"[LLM] Fallback to {fallback} succeeded")
            return result
        print(f"[LLM] Fallback {fallback} failed: {err}")
        fallback = MODEL_FALLBACKS.get(fallback)

    print(f"[LLM] All models failed. Last error: {err}")
    return None
