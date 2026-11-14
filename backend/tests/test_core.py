from pathlib import Path
import pytest
from app.context.builder import build_context, tokens
from app.execution.workspace import Workspace, BoundaryError
from app.execution.tools import Tools
from app.models.schemas import State
from app.orchestration.states import validate_transition, gates_current
from app.routing.router import Features, route
from app.routing.telemetry import estimated_cost


@pytest.mark.parametrize(
    "source,target",
    [
        ("CREATED", "ANALYZING"),
        ("TESTING", "REPAIRING"),
        ("SECURITY_REVIEW", "TESTING"),
        ("REPAIRING", "IMPLEMENTING"),
    ],
)
def test_valid_transitions(source, target):
    validate_transition(source, target)


@pytest.mark.parametrize(
    "source,target",
    [
        ("CREATED", "READY_FOR_REVIEW"),
        ("IMPLEMENTING", "FINAL_VERIFICATION"),
        ("FAILED", "ANALYZING"),
        ("READY_FOR_REVIEW", "FAILED"),
    ],
)
def test_invalid_transitions(source, target):
    with pytest.raises(ValueError):
        validate_transition(source, target)


@pytest.mark.parametrize(
    "policy,stage,expected",
    [
        ("small_only", "engineer", "small"),
        ("large_only", "tester", "large"),
        ("adaptive", "engineer", "medium"),
        ("adaptive", "tester", "small"),
    ],
)
def test_routing(policy, stage, expected):
    assert route(policy, Features(stage)).tier == expected


def test_security_floor_and_escalation():
    assert route("small_only", Features("engineer", security_critical=True)).tier == "medium"
    assert route("adaptive", Features("engineer", failures=1, failure_class="test_failure")).tier == "large"
    assert route("adaptive", Features("engineer", failures=1, failure_class="tool_error")).tier == "medium"
    assert route("adaptive", Features("tester", repository_files=600)).tier == "large"
    with pytest.raises(ValueError):
        route("adaptive", Features("tester", remaining_budget=0))


def test_context_preserves_essential_and_enforces_budget():
    context = build_context(
        "engineer",
        {"requirements": "Keep exact semantics", "failure": "assert 2 == 3"},
        [("large file", "a" * 50000)],
        200,
    )
    assert context.estimated_tokens <= 200
    assert "assert 2 == 3" in context.text and context.omitted
    with pytest.raises(ValueError):
        build_context("tester", {"requirements": "x" * 1000}, [], 10)


def test_usage_pricing_distinguishes_missing():
    table = '{"example":{"input_per_million":2,"output_per_million":4}}'
    assert estimated_cost(table, "example", 1000, 500) == 0.004
    assert estimated_cost(table, "unpriced", 1000, 500) is None
    assert estimated_cost(table, "example", None, 500) is None


def test_workspace_snapshot_and_path_permissions(tmp_path, repositories):
    ws, base = Workspace.create(str(repositories / "function"), repositories, tmp_path / "workspace")
    assert len(base) == 40
    assert not ws.diff()
    for path in ["../secret", ".env", "/etc/passwd", "tests/test_existing.py", "conftest.py"]:
        with pytest.raises(BoundaryError):
            ws.safe(path, writable=True)
    (ws.path / "link.py").symlink_to("/etc/passwd")
    with pytest.raises(BoundaryError):
        ws.safe("link.py")
    assert (repositories / "function" / "domain.py").read_text() == ws.safe("domain.py").read_text()


def test_role_permissions(tmp_path, repositories):
    ws, _ = Workspace.create(str(repositories / "function"), repositories, tmp_path / "ws")
    tools = Tools(ws, None, tmp_path, lambda: None)
    for role in ["planner", "security", "verifier", "tester"]:
        with pytest.raises(PermissionError):
            tools.call(role, "apply_patch", {"path": "domain.py", "content": "bad"})
    with pytest.raises(PermissionError):
        tools.call("engineer", "execute_command", {"command": ["sh", "-c", "id"]})
    with pytest.raises(BoundaryError):
        tools.call("tester", "write_test", {"name": "../escape.py", "content": "bad"})


def test_stale_validation():
    assert gates_current("a", "a", "a")
    assert not gates_current("b", "a", "a")
    assert not gates_current(None, None, None)


def test_recovery_cleanup_is_scoped_to_runtime(monkeypatch):
    from app.execution.sandbox import DockerSandbox
    import subprocess

    calls = []

    def run(args, **kwargs):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="aabbcc112233\n" if args[1] == "ps" else "")

    monkeypatch.setattr(subprocess, "run", run)
    DockerSandbox("image", owner="/allowed/runtime").cleanup_abandoned()
    assert calls[0] == ["docker", "ps", "-aq", "--filter", "label=forgeops.owner=/allowed/runtime"]
    assert calls[1] == ["docker", "rm", "-f", "aabbcc112233"]
