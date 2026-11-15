import json
import os
import uuid
import httpx
import pytest
from fastapi.testclient import TestClient
from app.config import Settings
from app.main import create_app
from app.providers.configuration import Credentials, ProviderSetup
from app.providers.store import ProviderStore
from app.providers.anthropic import AnthropicProvider
from app.providers.service import check_connection, discover_models


def setup_body(model="test-model", key="fake-local-test-key"):
    tier = {"model": model, "input_per_million": 1, "output_per_million": 2}
    return {
        "kind": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": key,
        "small": dict(tier),
        "medium": dict(tier),
        "large": dict(tier),
    }


def test_encrypted_settings_survive_restart_and_pin_active_run(setup):
    settings, _ = setup
    store = ProviderStore(settings)
    store.save(ProviderSetup(**setup_body()))
    assert ProviderStore(settings).effective().api_key == "fake-local-test-key"
    assert "fake-local-test-key" not in json.dumps(store.view())
    for path in store.root.iterdir():
        assert b"fake-local-test-key" not in path.read_bytes()
        assert path.stat().st_mode & 0o777 == 0o600
    assert store.root.stat().st_mode & 0o777 == 0o700
    run_id = str(uuid.uuid4())
    store.pin_run(run_id, store.effective())
    store.save(ProviderSetup(**setup_body("replacement-model", "new-fake-key")))
    assert store.for_run(run_id).model_small == "test-model"
    assert store.for_run(run_id).api_key == "fake-local-test-key"
    assert store.effective().model_small == "replacement-model"
    store.reset()
    assert store.for_run(run_id).api_key == "fake-local-test-key"
    store.forget_run(run_id)
    assert not (store.root / f"run-{run_id}.enc").exists()


def test_endpoint_change_cannot_reuse_saved_key(setup):
    settings, _ = setup
    store = ProviderStore(settings)
    store.save(ProviderSetup(**setup_body()))
    with pytest.raises(ValueError, match="new API key"):
        store.credential_values(Credentials(kind="openai", base_url="https://example.invalid/v1"))
    for value in [
        "file:///etc/passwd",
        "https://key@example.invalid/v1",
        "https://example.invalid/v1?key=secret",
        "http://example.invalid/v1",
    ]:
        with pytest.raises(ValueError):
            Credentials(base_url=value)
    assert Credentials(base_url="http://127.0.0.1:11434/v1").base_url.startswith("http:")


def test_provider_api_masks_secrets_and_validates_live_setup(setup, monkeypatch):
    settings, sessions = setup
    with TestClient(create_app(settings)) as client:
        assert not client.get("/api/provider").json()["configured"]
        body = setup_body()
        response = client.post("/api/provider", json=body)
        assert response.status_code == 200, response.text
        assert response.json()["configured"] and response.json()["key_saved"]
        assert body["api_key"] not in response.text
        assert body["api_key"] not in client.get("/api/provider").text
        invalid = {**body, "base_url": "http://untrusted.invalid/v1"}
        error = client.post("/api/provider", json=invalid)
        assert error.status_code == 422
        assert body["api_key"] not in error.text
        run = client.post(
            "/api/runs",
            json={
                "repository": str(settings.repository_root / "function"),
                "task": "Fix multiplication of price by quantity",
                "mode": "live",
            },
        )
        assert run.status_code == 201, run.text
        run_id = run.json()["id"]
        assert ProviderStore(settings).for_run(run_id).provider_kind == "anthropic"
        artifacts = client.get(f"/api/runs/{run_id}/artifacts")
        assert body["api_key"] not in artifacts.text
        assert artifacts.json()[0]["content"]["models"]["small"] == "test-model"
        assert client.get("/api/models").json()[0]["model"] == "test-model"
        monkeypatch.setattr("app.main.check_connection", lambda _: {"success": True, "model": "test-model"})
        assert client.post("/api/provider/test").json()["success"]
        assert client.post("/api/provider/reset").json()["configured"] is False


def test_provider_endpoints_require_instance_auth(setup):
    settings, _ = setup
    settings.api_token = "fake-access-token"
    with TestClient(create_app(settings)) as client:
        for path in ["/api/provider", "/api/provider/test", "/api/provider/models", "/api/provider/reset"]:
            response = client.get(path) if path == "/api/provider" else client.post(path, json={})
            assert response.status_code == 401


def test_anthropic_tool_loop_with_native_messages_and_usage():
    payloads = []
    totals = []
    settings = Settings(
        provider_kind="anthropic",
        provider_url="https://api.anthropic.com/v1",
        api_key="fake-key",
        pricing_json='{"test-model":{"input_per_million":1,"output_per_million":2}}',
    )

    def respond(request):
        assert request.url.path == "/v1/messages"
        assert request.headers["x-api-key"] == "fake-key"
        assert request.headers["anthropic-version"] == "2023-06-01"
        payloads.append(json.loads(request.content))
        content = (
            [{"type": "tool_use", "id": "one", "name": "list_directory", "input": {}}]
            if len(payloads) == 1
            else [
                {"type": "tool_use", "id": "two", "name": "submit_result", "input": {"summary": "complete"}}
            ]
        )
        return httpx.Response(
            200, json={"content": content, "usage": {"input_tokens": 100, "output_tokens": 20}}
        )

    client = httpx.Client(
        transport=httpx.MockTransport(respond),
        base_url="https://api.anthropic.com/v1/",
        headers={"x-api-key": "fake-key", "anthropic-version": "2023-06-01"},
    )

    class Tools:
        def call(self, role, name, args):
            assert role == "planner" and name == "list_directory"
            return ["domain.py"]

    result = AnthropicProvider(settings, client).invoke(
        "planner",
        "test-model",
        "Original requirements",
        Tools(),
        {"type": "object"},
        {
            "check": lambda: None,
            "request_budget": 10000,
            "remaining_budget": 1,
            "usage": lambda *args: totals.append(args),
        },
    )
    assert result.payload == {"summary": "complete"}
    assert result.calls == 2 and result.input_tokens == 200 and result.output_tokens == 40
    assert result.usage_source == "measured" and len(totals) == 2
    assert payloads[1]["messages"][-1]["content"][0]["tool_use_id"] == "one"
    assert all(t["name"] != "apply_patch" for t in payloads[0]["tools"])


def test_anthropic_budget_prevents_request():
    settings = Settings(pricing_json='{"test-model":{"input_per_million":20,"output_per_million":40}}')

    def unexpected(request):
        raise AssertionError("No request should be made")

    client = httpx.Client(transport=httpx.MockTransport(unexpected), base_url="https://example.invalid/")
    with pytest.raises(ValueError, match="budget"):
        AnthropicProvider(settings, client).invoke(
            "planner",
            "test-model",
            "requirements",
            None,
            {},
            {"check": lambda: None, "request_budget": 10000, "remaining_budget": 0.00001},
        )


@pytest.mark.parametrize("kind", ["openai", "anthropic"])
def test_connection_checks_and_model_discovery(kind):
    settings = Settings(
        provider_kind=kind,
        model_small="test-model",
        pricing_json='{"test-model":{"input_per_million":1,"output_per_million":2}}',
    )

    def respond(request):
        if request.method == "GET":
            return httpx.Response(
                200, json={"data": [{"id": "test-model", "display_name": "Current provider model"}]}
            )
        body = json.loads(request.content)
        assert (
            body["model"] == "test-model" and body.get("max_tokens", body.get("max_completion_tokens")) == 128
        )
        if kind == "anthropic":
            return httpx.Response(
                200,
                json={
                    "content": [{"type": "tool_use", "name": "connection_check", "input": {"ok": True}}],
                    "usage": {"input_tokens": 50, "output_tokens": 10},
                },
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {"function": {"name": "connection_check", "arguments": '{"ok":true}'}}
                            ]
                        }
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 10},
            },
        )

    client = httpx.Client(transport=httpx.MockTransport(respond), base_url="https://example.invalid/v1/")
    assert discover_models(kind, "", "", client)[0]["id"] == "test-model"
    result = check_connection(settings, client)
    assert result["success"] and result["estimated_cost"] == 0.00007


def test_provider_http_error_does_not_echo_provider_body_or_key(setup, monkeypatch):
    settings, _ = setup

    def fail(_):
        response = httpx.Response(
            401,
            text="fake-local-test-key",
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        )
        response.raise_for_status()

    monkeypatch.setattr("app.main.check_connection", fail)
    with TestClient(create_app(settings)) as client:
        client.post("/api/provider", json=setup_body())
        response = client.post("/api/provider/test")
        assert response.status_code == 502
        assert "401" in response.text and "fake-local-test-key" not in response.text


def test_saved_run_key_is_redacted_from_failure_artifacts(setup, monkeypatch):
    from test_workflow import DeterministicSandbox
    from app.database.models import Run

    settings, sessions = setup
    app = create_app(settings)
    app.state.workflow.sandbox = DeterministicSandbox()

    def fail_provider(current):
        raise RuntimeError("Example transport failure: " + current.api_key)

    monkeypatch.setattr("app.orchestration.engine.make_provider", fail_provider)
    with TestClient(app) as client:
        client.post("/api/provider", json=setup_body())
        response = client.post(
            "/api/runs",
            json={
                "repository": str(settings.repository_root / "function"),
                "task": "Correct multiplication of price by quantity",
                "mode": "live",
            },
        )
        assert response.status_code == 201
        run_id = response.json()["id"]
        app.state.workflow.execute(run_id)
        with sessions() as db:
            assert db.get(Run, run_id).status == "FAILED"
            assert "fake-local-test-key" not in db.get(Run, run_id).outcome
        assert "fake-local-test-key" not in client.get(f"/api/runs/{run_id}/events").text
        assert not (ProviderStore(settings).root / f"run-{run_id}.enc").exists()


@pytest.mark.skipif(os.environ.get("FORGEOPS_DOCKER_TESTS") != "1", reason="Real Docker sandbox required")
def test_native_anthropic_live_run_uses_saved_profile_and_all_five_roles(setup, monkeypatch):
    """Synthetic HTTP model responses, actual tools/orchestration/Docker gates."""
    from app.agents.prompts import PROMPTS
    from app.database.models import Run, Invocation
    from sqlalchemy import select

    settings, sessions = setup
    app = create_app(settings)
    criterion = "total(price, quantity) multiplies price by quantity, including zero quantity"
    roles = []

    def respond(request):
        payload = json.loads(request.content)
        role = next(name for name in PROMPTS if payload["system"].startswith(PROMPTS[name]))
        roles.append(role)
        assert payload["model"] == "test-model"
        assert request.headers["x-api-key"] == "fake-local-test-key"
        if role == "engineer" and len(payload["messages"]) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": "write",
                    "name": "apply_patch",
                    "input": {
                        "path": "domain.py",
                        "content": "def total(price, quantity):\n    return price * quantity\n\ndef average(values):\n    return sum(values) / len(values)\n",
                    },
                }
            ]
        elif role == "tester" and len(payload["messages"]) == 1:
            content = [
                {
                    "type": "tool_use",
                    "id": "test",
                    "name": "write_test",
                    "input": {
                        "name": "test_native_acceptance.py",
                        "content": "from domain import total\n\ndef test_requirement():\n    assert total(2.5, 4) == 10\n    assert total(4, 0) == 0\n",
                    },
                }
            ]
        else:
            output = {
                "summary": "Synthetic native-provider contract response",
                "criteria": {criterion: True},
                "recommendation": "review",
            }
            if role == "planner":
                output = {
                    "summary": "Fix multiplication",
                    "affected_files": ["domain.py"],
                    "steps": ["Implement multiplication"],
                    "acceptance_criteria": [criterion],
                    "risks": [],
                    "testing_strategy": "Independent numeric and zero-quantity cases",
                }
            content = [{"type": "tool_use", "id": "final", "name": "submit_result", "input": output}]
        return httpx.Response(
            200, json={"content": content, "usage": {"input_tokens": 100, "output_tokens": 20}}
        )

    def provider(current):
        client = httpx.Client(
            transport=httpx.MockTransport(respond),
            base_url=current.provider_url + "/",
            headers={"x-api-key": current.api_key},
        )
        return AnthropicProvider(current, client)

    monkeypatch.setattr("app.orchestration.engine.make_provider", provider)
    with TestClient(app) as client:
        client.post("/api/provider", json=setup_body())
        response = client.post(
            "/api/runs",
            json={
                "repository": str(settings.repository_root / "function"),
                "task": criterion,
                "mode": "live",
                "fixture": "function",
            },
        )
        assert response.status_code == 201, response.text
        run_id = response.json()["id"]
        app.state.workflow.execute(run_id)
        with sessions() as db:
            run = db.get(Run, run_id)
            assert run.status == "READY_FOR_REVIEW", run.outcome
            assert run.input_tokens == 700 and run.output_tokens == 140
            assert run.cost > 0 and run.patch_hash == run.security_hash == run.test_hash
            invocations = list(db.scalars(select(Invocation).where(Invocation.run_id == run_id)))
            assert {i.role for i in invocations} == set(PROMPTS)
            assert all(i.model == "test-model" and i.success for i in invocations)
        assert set(roles) == set(PROMPTS)
        assert "fake-local-test-key" not in client.get(f"/api/runs/{run_id}/artifacts").text


def test_benchmark_cli_loads_the_saved_instance_provider(setup, monkeypatch, tmp_path):
    import importlib.util
    import sys
    from pathlib import Path

    settings, _ = setup
    ProviderStore(settings).save(ProviderSetup(**setup_body()))
    source = Path(__file__).resolve().parents[2] / "benchmarks/run.py"
    spec = importlib.util.spec_from_file_location("dispatch_benchmark_provider_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    observed = []

    def evaluate(policy, fixture, mode, repositories, directory, provider_settings=None):
        assert provider_settings.provider_kind == "anthropic"
        assert provider_settings.api_key == "fake-local-test-key"
        observed.append(fixture)
        return {"policy": policy, "fixture": fixture, "verified_success": True, "wall_seconds": 0}

    monkeypatch.setattr(module, "evaluate", evaluate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "benchmarks/run.py",
            "--mode",
            "live",
            "--policies",
            "adaptive",
            "--provider-runtime",
            str(settings.runtime_dir),
            "--output",
            str(tmp_path / "synthetic-cli-test.json"),
        ],
    )
    module.main()
    assert len(observed) == 5
    assert "fake-local-test-key" not in (tmp_path / "synthetic-cli-test.json").read_text()


def test_missing_queued_snapshot_fails_instead_of_switching_provider(setup, monkeypatch):
    from test_workflow import DeterministicSandbox

    settings, _ = setup
    app = create_app(settings)
    app.state.workflow.sandbox = DeterministicSandbox()

    def unexpected(_):
        raise AssertionError("No model request should use a replacement provider")

    monkeypatch.setattr("app.orchestration.engine.make_provider", unexpected)
    with TestClient(app) as client:
        client.post("/api/provider", json=setup_body())
        response = client.post(
            "/api/runs",
            json={
                "repository": str(settings.repository_root / "function"),
                "task": "Fix multiplication of price by quantity",
                "mode": "live",
            },
        )
        assert response.status_code == 201
        run_id = response.json()["id"]
        ProviderStore(settings).forget_run(run_id)
        app.state.workflow.execute(run_id)
        run = client.get(f"/api/runs/{run_id}").json()["run"]
        assert run["status"] == "FAILED" and "snapshot" in run["outcome"].lower()
