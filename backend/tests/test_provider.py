import httpx
import pytest
from app.agents.provider import OpenAIProvider
from app.config import Settings


@pytest.mark.parametrize(
    "provider_url,token_field",
    [
        ("https://api.openai.com/v1", "max_completion_tokens"),
        ("https://openrouter.ai/api/v1", "max_tokens"),
        ("http://127.0.0.1:11434/v1", "max_tokens"),
    ],
)
def test_openai_compatible_structured_tool_path_and_usage(provider_url, token_field):
    calls = []
    usage = []

    def handle(request):
        import json

        payload = json.loads(request.content)
        calls.append(payload)
        assert payload[token_field] == 3000
        assert (
            ("max_tokens" not in payload)
            if token_field == "max_completion_tokens"
            else ("max_completion_tokens" not in payload)
        )
        message = (
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "one",
                        "type": "function",
                        "function": {"name": "list_directory", "arguments": "{}"},
                    }
                ],
            }
            if len(calls) == 1
            else {"role": "assistant", "content": '{"summary":"done"}'}
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": message}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    settings = Settings(
        api_key="not-a-real-key",
        provider_url=provider_url,
        pricing_json='{"test-model":{"input_per_million":1,"output_per_million":2}}',
    )
    client = httpx.Client(transport=httpx.MockTransport(handle), base_url="https://example.invalid/v1/")

    class Tools:
        def call(self, role, name, args):
            return ["main.py"]

    result = OpenAIProvider(settings, client).invoke(
        "planner",
        "test-model",
        "requirements",
        Tools(),
        {},
        {
            "check": lambda: None,
            "request_budget": 10000,
            "remaining_budget": 1,
            "usage": lambda *x: usage.append(x),
        },
    )
    assert result.payload == {"summary": "done"} and result.calls == 2
    assert result.input_tokens == 200 and result.usage_source == "measured"
    assert len(usage) == 2 and calls[1]["messages"][-1]["role"] == "tool"


def test_provider_refuses_unpriced_requests():
    settings = Settings(api_key="not-a-real-key")
    provider = OpenAIProvider(settings, httpx.Client(base_url="https://example.invalid/v1/"))
    with pytest.raises(ValueError, match="pricing"):
        provider.invoke(
            "planner",
            "unpriced",
            "requirements",
            None,
            {},
            {"check": lambda: None, "request_budget": 10000, "remaining_budget": 1},
        )


def test_budget_reservation_prevents_network_call():
    def fail_if_called(request):
        raise AssertionError("Network must not be called without budget")

    settings = Settings(pricing_json='{"expensive":{"input_per_million":50,"output_per_million":200}}')
    provider = OpenAIProvider(
        settings,
        httpx.Client(transport=httpx.MockTransport(fail_if_called), base_url="https://example.invalid/"),
    )
    with pytest.raises(ValueError, match="budget"):
        provider.invoke(
            "planner",
            "expensive",
            "requirements",
            None,
            {},
            {"check": lambda: None, "request_budget": 10000, "remaining_budget": 0.00001},
        )
