import json
from pathlib import Path
from sqlalchemy import select
from app.agents.provider import ScriptedProvider
from app.database.models import Run, Artifact, Event, Invocation
from app.models.schemas import RunCreate
from app.orchestration.engine import Engine
from app.execution.sandbox import CommandResult


class DeterministicSandbox:
    """Explicit command fixture; Docker integration is exercised separately."""

    def available(self):
        return True

    def execute(self, workspace, command, validation=None, check=None):
        if check:
            check()
        if command[0] == "bandit":
            insecure = "eval(" in (workspace / "domain.py").read_text()
            return CommandResult(
                command,
                1 if insecure else 0,
                json.dumps(
                    {
                        "errors": [],
                        "results": [
                            {
                                "issue_severity": "MEDIUM",
                                "issue_text": "eval unsafe",
                                "filename": "domain.py",
                                "line_number": 2,
                                "code": "eval(...)",
                            }
                        ]
                        if insecure
                        else [],
                    }
                ),
            )
        content = (workspace / "main.py").read_text()
        failed = "Field(ge=0)" in content and "quantity: int = Field(ge=0)" in content
        return CommandResult(command, 1 if failed else 0, "FAILED expected 422" if failed else "2 passed")


def create(sessions, repository, **kwargs):
    with sessions() as db:
        r = Run(
            **RunCreate(
                repository=str(repository),
                task="Fix quote multiplication; validate quantities; enforce ownership; handle empty average.",
                **kwargs,
            ).model_dump()
        )
        db.add(r)
        db.commit()
        return r.id


def test_e2e_repair_and_telemetry(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo")
    Engine(settings, sessions, sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "READY_FOR_REVIEW", r.outcome
        assert r.retries == 2 and r.patch_hash == r.security_hash == r.test_hash
        artifacts = list(db.scalars(select(Artifact).where(Artifact.run_id == rid)))
        assert len([a for a in artifacts if a.kind == "patch"]) == 3
        assert any(a.kind == "security_results" and not a.content["passed"] for a in artifacts)
        assert any(a.kind == "test_results" and not a.content["passed"] for a in artifacts)
        assert any(a.kind == "generated_tests" for a in artifacts)
        assert {i.role for i in db.scalars(select(Invocation))} == {
            "planner",
            "engineer",
            "security",
            "tester",
            "verifier",
        }
        assert r.input_tokens == 0 and r.cost == 0
        assert not (settings.runtime_dir / "runs" / rid / "workspace").exists()


def test_repair_limit(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo", max_repairs=0)
    Engine(settings, sessions, sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "FAILED" and "repair" in r.outcome
        assert r.test_hash is None


def test_cancel_and_recovery(setup):
    settings, sessions = setup
    cancelled = create(sessions, settings.repository_root / "demo")
    active = create(sessions, settings.repository_root / "demo")
    queued = create(sessions, settings.repository_root / "demo")
    with sessions() as db:
        db.get(Run, cancelled).cancel_requested = True
        db.get(Run, active).status = "IMPLEMENTING"
        db.commit()
    engine = Engine(settings, sessions, sandbox=DeterministicSandbox())
    assert engine.recover() == 1
    engine.execute(cancelled)
    with sessions() as db:
        assert db.get(Run, cancelled).status == "CANCELLED"
        assert db.get(Run, active).status == "FAILED"
        assert db.get(Run, queued).status == "CREATED"


def test_tool_budget_and_no_host_fallback(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo", max_tool_calls=1)
    Engine(settings, sessions, sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        assert db.get(Run, rid).status == "FAILED"
        assert "Tool call" in db.get(Run, rid).outcome
    sandbox = DeterministicSandbox()
    sandbox.available = lambda: False
    rid = create(sessions, settings.repository_root / "demo")
    Engine(settings, sessions, sandbox=sandbox).execute(rid)
    with sessions() as db:
        assert "host execution" in db.get(Run, rid).outcome


class RepeatingProvider(ScriptedProvider):
    def invoke(self, role, model, context, tools, schema, metadata):
        return super().invoke(role, model, context, tools, schema, {**metadata, "attempt": 0})


def test_repeated_unsuccessful_cycle_terminates(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo", max_repairs=5)
    Engine(settings, sessions, provider=RepeatingProvider(), sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "FAILED" and "Repeated unsuccessful" in r.outcome
        assert r.retries == 1


def test_stale_gate_cannot_be_overridden(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo")
    with sessions() as db:
        r = db.get(Run, rid)
        r.status = "FINAL_VERIFICATION"
        r.patch_hash = "b"
        r.security_hash = "a"
        r.test_hash = "a"
        db.commit()
    import pytest

    with pytest.raises(ValueError, match="Stale"):
        Engine(settings, sessions, sandbox=DeterministicSandbox()).transition(rid, "READY_FOR_REVIEW")


def test_elapsed_time_limit(setup, monkeypatch):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo", max_seconds=1)
    clock = iter(range(1000))
    monkeypatch.setattr("app.orchestration.engine.time.monotonic", lambda: next(clock))
    Engine(settings, sessions, sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "FAILED" and "execution time" in r.outcome


def test_partial_engineering_failure_invalidates_approvals(setup):
    settings, sessions = setup

    class PartialProvider(ScriptedProvider):
        def invoke(self, role, model, context, tools, schema, metadata):
            if role == "engineer":
                tools.call(
                    "engineer",
                    "apply_patch",
                    {"path": "domain.py", "content": "def total(p,q): return p*q\n"},
                )
                raise RuntimeError("Provider interrupted after writing")
            return super().invoke(role, model, context, tools, schema, metadata)

    rid = create(sessions, settings.repository_root / "demo")
    with sessions() as db:
        r = db.get(Run, rid)
        r.security_hash = r.test_hash = "stale"
        db.commit()
    Engine(settings, sessions, provider=PartialProvider(), sandbox=DeterministicSandbox()).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "FAILED" and r.security_hash is None and r.test_hash is None
        invocation = db.scalar(
            select(Invocation).where(Invocation.run_id == rid, Invocation.role == "engineer")
        )
        assert not invocation.success and invocation.failure_class == "RuntimeError"


def test_cancellation_at_readiness_cannot_be_ignored(setup):
    settings, sessions = setup
    rid = create(sessions, settings.repository_root / "demo")
    with sessions() as db:
        r = db.get(Run, rid)
        r.status = "FINAL_VERIFICATION"
        r.patch_hash = r.security_hash = r.test_hash = "valid"
        r.cancel_requested = True
        db.commit()
    import pytest
    from app.orchestration.engine import Cancelled

    with pytest.raises(Cancelled):
        Engine(settings, sessions).transition(rid, "READY_FOR_REVIEW")
