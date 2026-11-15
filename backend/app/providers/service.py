import json
import math
import httpx
from app.agents.provider import OpenAIProvider, output_limit
from app.providers.anthropic import AnthropicProvider
from app.providers.configuration import Credentials
from app.routing.telemetry import estimated_cost


def make_provider(settings):
    Credentials(kind=settings.provider_kind, base_url=settings.provider_url)
    if settings.provider_kind == "anthropic":
        return AnthropicProvider(settings)
    if settings.provider_kind == "openai":
        return OpenAIProvider(settings)
    raise ValueError("Unsupported provider type")


def client_for(kind, base_url, key):
    headers = (
        {"x-api-key": key, "anthropic-version": "2023-06-01"}
        if kind == "anthropic"
        else {"Authorization": f"Bearer {key}"}
    )
    return httpx.Client(base_url=base_url.rstrip("/") + "/", headers=headers, timeout=20)


def discover_models(kind, base_url, key, client=None):
    owned = client is None
    client = client or client_for(kind, base_url, key)
    try:
        response = client.get("models")
        response.raise_for_status()
        result = []
        for item in response.json().get("data", [])[:300]:
            identifier = item.get("id")
            if not isinstance(identifier, str):
                continue
            entry = {"id": identifier, "name": item.get("display_name") or item.get("name") or identifier}
            pricing = item.get("pricing") or {}
            try:
                if not all(
                    math.isfinite(float(pricing[k])) and float(pricing[k]) >= 0
                    for k in ["prompt", "completion"]
                ):
                    raise ValueError("Invalid provider pricing")
                entry.update(
                    {
                        "input_per_million": float(pricing["prompt"]) * 1_000_000,
                        "output_per_million": float(pricing["completion"]) * 1_000_000,
                    }
                )
            except (ValueError, KeyError, TypeError):
                pass
            result.append(entry)
        return result
    finally:
        if owned:
            client.close()


def check_connection(settings, client=None):
    owned = client is None
    client = client or client_for(settings.provider_kind, settings.provider_url, settings.api_key)
    model = settings.model_small
    tool = {
        "name": "connection_check",
        "description": "Confirm tool calling works.",
        "parameters": {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        },
    }
    try:
        if settings.provider_kind == "anthropic":
            response = client.post(
                "messages",
                json={
                    "model": model,
                    "max_tokens": 128,
                    "messages": [{"role": "user", "content": "Call connection_check with ok=true."}],
                    "tools": [
                        {
                            "name": tool["name"],
                            "description": tool["description"],
                            "input_schema": tool["parameters"],
                        }
                    ],
                    "tool_choice": {"type": "tool", "name": tool["name"]},
                },
            )
            response.raise_for_status()
            data = response.json()
            passed = any(
                p.get("type") == "tool_use"
                and p.get("name") == tool["name"]
                and p.get("input", {}).get("ok") is True
                for p in data.get("content", [])
            )
            usage = data.get("usage") or {}
            input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        else:
            response = client.post(
                "chat/completions",
                json={
                    "model": model,
                    **output_limit(settings, 128),
                    "messages": [{"role": "user", "content": "Call connection_check with ok=true."}],
                    "tools": [{"type": "function", "function": tool}],
                    "tool_choice": {"type": "function", "function": {"name": tool["name"]}},
                },
            )
            response.raise_for_status()
            data = response.json()
            calls = data.get("choices", [{}])[0].get("message", {}).get("tool_calls", [])
            passed = any(
                p.get("function", {}).get("name") == tool["name"]
                and json.loads(p["function"].get("arguments", "{}")).get("ok") is True
                for p in calls
            )
            usage = data.get("usage") or {}
            input_tokens, output_tokens = usage.get("prompt_tokens"), usage.get("completion_tokens")
        if not passed:
            raise ValueError("Provider responded but the tool-calling check did not pass")
        return {
            "success": True,
            "model": model,
            "message": "Authentication and tool-calling check passed. Run a live workflow to verify the full pipeline.",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "estimated_cost": estimated_cost(settings.pricing_json, model, input_tokens, output_tokens),
        }
    finally:
        if owned:
            client.close()
