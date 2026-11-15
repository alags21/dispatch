import hashlib
import importlib
import json
from pathlib import Path
import time
from sqlalchemy import select
from app.agents.provider import ScriptedProvider
from app.providers.service import make_provider
from app.providers.store import ProviderStore
from app.context.builder import build_context
from app.database.models import Artifact, Event, Invocation, Run, now
from app.evaluation.gates import security_gate, test_gate
from app.execution.sandbox import DockerSandbox
from app.execution.tools import Tools
from app.execution.workspace import Workspace
from app.models.schemas import State
from app.orchestration.states import TERMINAL, gates_current, validate_transition
from app.routing.router import Features, route


class Cancelled(Exception):
    pass


class LimitExceeded(RuntimeError):
    pass


class Engine:
    def __init__(self, settings, sessions, provider=None, sandbox=None, preserve_workspace=False):
        self.settings, self.sessions = settings, sessions
        self.preserve_workspace = preserve_workspace
        self.provider_override = provider
        self.sandbox = sandbox or DockerSandbox(
            settings.sandbox_image, settings.command_timeout, str(settings.runtime_dir.resolve())
        )

    def transition(self, run_id, target, detail=None):
        with self.sessions() as db:
            run = db.get(Run, run_id)
            validate_transition(run.status, target)
            if target == State.READY_FOR_REVIEW and run.cancel_requested:
                raise Cancelled("Cancellation requested before readiness")
            if target == State.READY_FOR_REVIEW and not gates_current(
                run.patch_hash, run.security_hash, run.test_hash
            ):
                raise ValueError("Stale or missing validation approvals")
            run.status = target
            if target in TERMINAL:
                run.ended_at = now()
            db.add(Event(run_id=run_id, state=target, detail=detail or {}))
            db.commit()

    def artifact(self, run_id, kind, content, digest=None):
        with self.sessions() as db:
            db.add(Artifact(run_id=run_id, kind=kind, content=content, patch_hash=digest))
            db.commit()

    def recover(self):
        cleanup = getattr(self.sandbox, "cleanup_abandoned", None)
        if cleanup and self.sandbox.available():
            cleanup()
        # Queued CREATED jobs remain durable. Interrupted jobs fail closed, rather than repeat side effects.
        with self.sessions() as db:
            interrupted = list(db.scalars(select(Run).where(Run.status.not_in([*TERMINAL, State.CREATED]))))
        for run in interrupted:
            self.transition(
                run.id,
                State.FAILED,
                {
                    "failure_class": "interrupted",
                    "message": "Worker restart; artifacts retained. Submit a new run.",
                },
            )
            with self.sessions() as db:
                record = db.get(Run, run.id)
                record.outcome = "Interrupted execution: mandatory gates must run again in a new run"
                db.commit()
            ProviderStore(self.settings).forget_run(run.id)
        return len(interrupted)

    def execute(self, run_id):
        started = time.monotonic()
        with self.sessions() as db:
            r = db.get(Run, run_id)
            if r.status != State.CREATED:
                return
            r.started_at = now()
            db.commit()
            spec = {c.name: getattr(r, c.name) for c in Run.__table__.columns}
        workspace = None
        provider = None
        execution_settings = self.settings
        provider_store = ProviderStore(self.settings)

        def check():
            with self.sessions() as db:
                current = db.get(Run, run_id)
                if current.cancel_requested:
                    raise Cancelled("Cancellation requested")
                if time.monotonic() - started > current.max_seconds:
                    raise LimitExceeded("Run execution time exhausted")
                if current.cost > current.max_budget:
                    raise LimitExceeded("Model budget exhausted")

        def tick():
            check()
            with self.sessions() as db:
                current = db.get(Run, run_id)
                if current.tool_calls >= current.max_tool_calls:
                    raise LimitExceeded("Tool call limit exhausted")
                current.tool_calls += 1
                db.commit()

        def audit(role, name, args, result):
            # Capture reviewable evidence without retaining whole repeated file reads.
            self.artifact(
                run_id,
                "tool",
                {
                    "role": role,
                    "name": name,
                    "path": args.get("path") or args.get("name"),
                    "result": str(result)[:5000],
                },
            )

        try:
            check()
            self.transition(run_id, State.ANALYZING)
            if not self.sandbox.available():
                raise RuntimeError("Docker sandbox image unavailable; refusing unrestricted host execution")
            run_dir = self.settings.runtime_dir.resolve() / "runs" / run_id
            workspace, base = Workspace.create(
                spec["repository"],
                self.settings.repository_root,
                run_dir / "workspace",
                self.settings.max_repo_files,
                self.settings.max_repo_bytes,
            )
            validation = run_dir / "validation"
            validation.mkdir()
            validation.chmod(0o755)
            with self.sessions() as db:
                db.get(Run, run_id).base_commit = base
                db.commit()
            tools = Tools(workspace, self.sandbox, validation, tick, audit)
            if spec["mode"] == "live":
                with self.sessions() as db:
                    pinned = (
                        db.scalar(
                            select(Artifact.id).where(Artifact.run_id == run_id, Artifact.kind == "provider")
                        )
                        is not None
                    )
                execution_settings = provider_store.for_run(run_id, require_snapshot=pinned)
            provider = self.provider_override or (
                ScriptedProvider() if spec["mode"] == "scripted" else make_provider(execution_settings)
            )
            plan, feedback, failure_class = {}, {}, None
            attempt = 0
            observations = set()

            def invoke(role):
                check()
                module = importlib.import_module(f"app.agents.{role}")
                essentials = {"original_requirements": spec["task"], "mode": spec["mode"]}
                if role != "planner":
                    essentials["implementation_plan"] = plan
                if role in {"engineer", "verifier"}:
                    essentials["actionable_evidence"] = feedback
                if role == "verifier":
                    with self.sessions() as db:
                        history = db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.id))
                        essentials["execution_history"] = [
                            {
                                "state": e.state,
                                "timestamp": e.timestamp,
                                "failure_class": e.detail.get("failure_class"),
                            }
                            for e in history
                        ]
                optional = []
                filenames = workspace.files()
                if role == "planner":
                    optional.append(("repository map", "\n".join(filenames)))
                if role in {"security", "tester", "verifier"}:
                    optional.append(("current patch", workspace.diff()))
                if role in {"planner", "engineer", "security", "tester"}:
                    selected = list(
                        dict.fromkeys(
                            (
                                plan.get("affected_files", [])
                                + [
                                    f
                                    for f in filenames
                                    if f
                                    in {
                                        "AGENTS.md",
                                        "README.md",
                                        "requirements.txt",
                                        "package.json",
                                        "pyproject.toml",
                                    }
                                ]
                                + filenames
                            )
                        )
                    )
                    for filename in selected[:18]:
                        try:
                            optional.append((filename, workspace.safe(filename).read_text()[:18000]))
                        except (OSError, ValueError, UnicodeError):
                            pass
                if role == "security":
                    essentials["security_policy"] = (
                        "No credential changes, unsafe eval/shell, or weakened authorization. Scanner medium+ blocks."
                    )
                stage_budget = int(
                    json.loads(self.settings.context_budgets_json).get(role, self.settings.context_budget)
                )
                stage_budget = min(stage_budget, self.settings.context_budget)
                context = build_context(role, essentials, optional, max(1, stage_budget - 3000))
                with self.sessions() as db:
                    remaining = spec["max_budget"] - db.get(Run, run_id).cost
                critical = any(
                    x in spec["task"].lower() for x in ["auth", "security", "permission", "secret", "owner"]
                )
                decision = route(
                    spec["policy"],
                    Features(
                        role,
                        complexity=min(3, len(plan.get("affected_files", []))),
                        affected_files=len(plan.get("affected_files", [])),
                        repository_files=len(filenames),
                        security_critical=critical,
                        context_tokens=context.estimated_tokens,
                        failures=attempt,
                        failure_class=failure_class,
                        remaining_budget=remaining,
                    ),
                    self.settings.security_minimum_tier,
                )
                model = (
                    "scripted-fixture-oracle"
                    if spec["mode"] == "scripted"
                    else getattr(execution_settings, f"model_{decision.tier}")
                )
                if not model:
                    raise ValueError(f"No model configured for tier {decision.tier}")
                with self.sessions() as db:
                    invocation = Invocation(
                        run_id=run_id,
                        role=role,
                        model=model,
                        tier=decision.tier,
                        routing_reason=decision.reason,
                        context_tokens=context.estimated_tokens,
                        usage_source="scripted" if spec["mode"] == "scripted" else "missing",
                        latency_ms=0,
                        attempt=attempt,
                        success=False,
                    )
                    db.add(invocation)
                    db.commit()
                    invocation_id = invocation.id
                t0 = time.monotonic()

                def usage(input_tokens, output_tokens, cost, measured):
                    with self.sessions() as db:
                        record = db.get(Invocation, invocation_id)
                        record.input_tokens = (record.input_tokens or 0) + input_tokens
                        record.output_tokens = (record.output_tokens or 0) + output_tokens
                        record.cost = (record.cost or 0) + cost
                        record.usage_source = "measured" if measured else "estimated"
                        run = db.get(Run, run_id)
                        run.input_tokens += input_tokens
                        run.output_tokens += output_tokens
                        run.cost += cost
                        db.commit()

                try:
                    result = provider.invoke(
                        role,
                        model,
                        context.text,
                        tools,
                        module.OUTPUT_SCHEMA.model_json_schema(),
                        {
                            "fixture": spec["fixture"],
                            "task": spec["task"],
                            "attempt": attempt,
                            "check": check,
                            "request_budget": stage_budget,
                            "remaining_budget": remaining,
                            "usage": usage,
                        },
                    )
                    output = module.validate(result.payload).model_dump()
                    with self.sessions() as db:
                        record = db.get(Invocation, invocation_id)
                        record.success = True
                        record.latency_ms = (time.monotonic() - t0) * 1000
                        db.commit()
                    self.artifact(
                        run_id,
                        role,
                        {
                            "invocation_id": invocation_id,
                            "output": output,
                            "context": {
                                "estimated_tokens": context.estimated_tokens,
                                "omitted": context.omitted,
                            },
                            "model_calls": result.calls,
                        },
                    )
                    return output
                except Exception as exc:
                    with self.sessions() as db:
                        record = db.get(Invocation, invocation_id)
                        record.latency_ms = (time.monotonic() - t0) * 1000
                        record.failure_class = type(exc).__name__
                        db.commit()
                    raise

            self.transition(run_id, State.PLANNING)
            plan = invoke("planner")
            self.transition(run_id, State.IMPLEMENTING)
            while True:
                check()
                # Invalidate before any engineering tools can modify the patch, including on partial failures.
                with self.sessions() as db:
                    run = db.get(Run, run_id)
                    run.security_hash = run.test_hash = None
                    db.commit()
                engineer = invoke("engineer")
                if (workspace.path / "tests").is_dir():
                    tick()
                    development = self.sandbox.execute(
                        workspace.path, ["pytest", "-q", "-p", "no:cacheprovider", "tests"], check=check
                    )
                    self.artifact(run_id, "development_check", development.dump())
                diff = workspace.diff()
                digest = hashlib.sha256(diff.encode()).hexdigest()
                with self.sessions() as db:
                    db.get(Run, run_id).patch_hash = digest
                    db.commit()
                self.artifact(
                    run_id,
                    "patch",
                    {
                        "diff": diff,
                        "changed_files": workspace.changed(),
                        "summary": engineer["summary"],
                        "version": attempt + 1,
                    },
                    digest,
                )
                if not diff:
                    raise ValueError("Engineer produced no reviewable changes")
                if len(diff.encode()) > self.settings.max_repo_bytes:
                    raise LimitExceeded("Patch exceeds configured artifact size limit")
                self.transition(run_id, State.SECURITY_REVIEW, {"patch_hash": digest})
                security_analysis = invoke("security")
                tick()
                findings, scanner_results = security_gate(
                    workspace, self.sandbox, check, self.settings.semgrep_enabled
                )
                # Never allow LLM findings to masquerade as deterministic scanner evidence.
                advisory = [{**f, "source": "llm", "verified": False} for f in security_analysis["findings"]]
                findings_json = [f.model_dump() for f in findings] + advisory
                security_ok = not any(f["severity"] in {"medium", "high", "critical"} for f in findings_json)
                self.artifact(
                    run_id,
                    "security_results",
                    {"passed": security_ok, "findings": findings_json, "scanners": scanner_results},
                    digest,
                )
                if workspace.digest() != digest:
                    raise ValueError("Patch changed during read-only security review")
                if not security_ok:
                    feedback = {"security_findings": findings_json}
                    failure_class = "security_failure"
                else:
                    with self.sessions() as db:
                        db.get(Run, run_id).security_hash = digest
                        db.commit()
                    self.transition(run_id, State.TESTING, {"patch_hash": digest})
                    invoke("tester")
                    generated = (
                        {p.name: p.read_text() for p in (validation / "generated").glob("*.py")}
                        if (validation / "generated").exists()
                        else {}
                    )
                    if not generated:
                        raise ValueError("Tester must produce independent reviewable tests")
                    self.artifact(run_id, "generated_tests", generated, digest)
                    tick()
                    tests = test_gate(workspace, self.sandbox, validation, check)
                    self.artifact(run_id, "test_results", tests, digest)
                    if workspace.digest() != digest:
                        raise ValueError("Patch changed during test gate")
                    if tests["passed"]:
                        with self.sessions() as db:
                            db.get(Run, run_id).test_hash = digest
                            db.commit()
                        feedback = {
                            "security": {"passed": True, "findings": findings_json},
                            "tests": tests,
                            "patch_hash": digest,
                        }
                        self.transition(run_id, State.FINAL_VERIFICATION)
                        report = invoke("verifier")
                        ready = (
                            report["recommendation"] == "review"
                            and bool(report["criteria"])
                            and all(report["criteria"].get(c) is True for c in plan["acceptance_criteria"])
                        )
                        report.update(
                            {
                                "patch_hash": digest,
                                "base_commit": base,
                                "test_evidence": tests,
                                "patch_summary": engineer["summary"],
                                "security_findings": findings_json,
                                "human_review_requirements": [
                                    "Review patch and generated tests",
                                    "Verify deployment-specific authorization and dependencies",
                                ],
                                "evidence_mode": spec["mode"],
                            }
                        )
                        self.artifact(run_id, "final_report", report, digest)
                        check()
                        if workspace.digest() != digest or not ready:
                            raise ValueError("Final verification rejected readiness or patch changed")
                        with self.sessions() as db:
                            db.get(Run, run_id).outcome = "Review-ready recommendation; no merge performed"
                            db.commit()
                        self.transition(run_id, State.READY_FOR_REVIEW)
                        break
                    feedback = {"test_failures": tests}
                    failure_class = "test_failure"
                fingerprint = (digest, failure_class)
                if fingerprint in observations:
                    raise LimitExceeded("Repeated unsuccessful patch and feedback; no useful progress")
                observations.add(fingerprint)
                if attempt >= spec["max_repairs"]:
                    raise LimitExceeded("Maximum repair attempts exhausted")
                attempt += 1
                with self.sessions() as db:
                    db.get(Run, run_id).retries = attempt
                    db.commit()
                self.transition(
                    run_id,
                    State.REPAIRING,
                    {"attempt": attempt, "failure_class": failure_class, "feedback": feedback},
                )
                self.transition(run_id, State.IMPLEMENTING)
        except Exception as exc:
            target = State.CANCELLED if isinstance(exc, Cancelled) else State.FAILED
            # Do not return provider headers or credentials in persisted error messages.
            message = str(exc)[:2000]
            if execution_settings.api_key:
                message = message.replace(execution_settings.api_key, "[redacted]")
            with self.sessions() as db:
                run = db.get(Run, run_id)
                run.outcome = message
                db.commit()
            self.transition(run_id, target, {"failure_class": type(exc).__name__, "message": message})
        finally:
            if provider is not self.provider_override and getattr(provider, "client", None) is not None:
                provider.client.close()
            provider_store.forget_run(run_id)
            # Patches/logs/tests live in the DB. Discard code copies on success/cancel; retain failed workspaces for diagnosis.
            with self.sessions() as db:
                status = db.get(Run, run_id).status
            if (
                workspace
                and not self.preserve_workspace
                and status in {State.READY_FOR_REVIEW, State.CANCELLED}
            ):
                workspace.cleanup()
