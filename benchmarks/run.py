"""Reproducible comparisons with independently maintained validation; no live calls by default."""

import argparse
import importlib.util
import json
from pathlib import Path
import re
import shutil
import statistics
import tempfile
import time
from sqlalchemy import select
from app.config import Settings
from app.providers.store import ProviderStore
from app.database.models import Base, Run, Invocation, Artifact
from app.database.session import database
from app.evaluation.gates import test_gate
from app.execution.sandbox import DockerSandbox
from app.execution.workspace import Workspace
from app.models.schemas import RunCreate
from app.orchestration.engine import Engine

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("prepare", ROOT / "demo/prepare.py")
prepare_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare_module)


def evaluate(policy, fixture, mode, repositories, directory, provider_settings=None):
    task = json.loads(
        (ROOT / "benchmarks/fixtures" / fixture / "task.json").read_text()
    )
    base = provider_settings or Settings()
    settings = base.model_copy(
        update={
            "database_url": f"sqlite:///{directory}/bench.db",
            "runtime_dir": directory / "runtime",
            "repository_root": repositories,
            "worker_enabled": False,
        }
    )
    settings.prepare()
    db_engine, sessions = database(settings.database_url)
    Base.metadata.create_all(db_engine)
    with sessions() as db:
        r = Run(
            **RunCreate(
                repository=str(repositories / fixture),
                task=task["description"],
                policy=policy,
                fixture=fixture,
                mode=mode,
            ).model_dump()
        )
        db.add(r)
        db.commit()
        rid = r.id
    sandbox = DockerSandbox(settings.sandbox_image, settings.command_timeout)
    t0 = time.monotonic()
    Engine(settings, sessions, sandbox=sandbox, preserve_workspace=True).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        invocations = list(
            db.scalars(select(Invocation).where(Invocation.run_id == rid))
        )
        artifacts = list(db.scalars(select(Artifact).where(Artifact.run_id == rid)))
        ws = Workspace(directory / "runtime/runs" / rid / "workspace")
        validation = directory / "independent"
        shutil.copytree(
            ROOT / "benchmarks/fixtures" / fixture / "validation", validation
        )
        validation.chmod(0o755)
        for p in validation.rglob("*"):
            p.chmod(0o755 if p.is_dir() else 0o644)
        tests = (
            test_gate(ws, sandbox, validation)
            if ws.path.exists()
            else {"passed": False, "stdout": "No patch workspace"}
        )
        passed = re.search(r"(\d+) passed", tests["stdout"])
        failed = re.search(r"(\d+) failed", tests["stdout"])
        return {
            "fixture": fixture,
            "policy": policy,
            "mode": mode,
            "verified_success": r.status == "READY_FOR_REVIEW" and tests["passed"],
            "run_status": r.status,
            "outcome": r.outcome,
            "security_violations_detected": sum(
                len(a.content["findings"])
                for a in artifacts
                if a.kind == "security_results"
            ),
            "tests_passed": int(passed.group(1)) if passed else 0,
            "tests_failed": int(failed.group(1))
            if failed
            else (0 if tests["passed"] else 1),
            "model_calls": 0
            if mode == "scripted"
            else sum(
                a.content.get("model_calls", 0)
                for a in artifacts
                if a.kind in {"planner", "engineer", "security", "tester", "verifier"}
            ),
            "agent_invocations": len(invocations),
            "input_tokens": None if mode == "scripted" else r.input_tokens,
            "output_tokens": None if mode == "scripted" else r.output_tokens,
            "estimated_api_cost": None if mode == "scripted" else r.cost,
            "usage_source": "scripted_no_api_usage"
            if mode == "scripted"
            else "provider_usage",
            "wall_seconds": round(time.monotonic() - t0, 3),
            "repair_iterations": r.retries,
            "tiers": [i.tier for i in invocations],
            "validation_output": tests["stdout"],
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policies",
        nargs="+",
        default=["small_only", "large_only", "adaptive"],
        choices=["small_only", "large_only", "adaptive"],
    )
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--mode", choices=["scripted", "live"], default="scripted")
    parser.add_argument("--output", default=str(ROOT / "benchmarks/report.json"))
    parser.add_argument(
        "--provider-runtime",
        help="Instance runtime directory containing saved UI provider settings",
    )
    args = parser.parse_args()
    provider_settings = (
        ProviderStore(Settings(runtime_dir=Path(args.provider_runtime))).effective()
        if args.provider_runtime
        else None
    )
    if args.repeats < 1:
        parser.error("repeats must be positive")
    results = []
    with tempfile.TemporaryDirectory(prefix="forgeops-benchmark-") as temp:
        temp = Path(temp)
        temp.chmod(0o755)
        repositories = prepare_module.prepare(temp / "repos")
        for repeat in range(args.repeats):
            for policy in args.policies:
                for fixture in [
                    "function",
                    "validation",
                    "authorization",
                    "edge",
                    "feature",
                ]:
                    directory = temp / f"{repeat}-{policy}-{fixture}"
                    directory.mkdir(mode=0o755)
                    result = evaluate(
                        policy,
                        fixture,
                        args.mode,
                        repositories,
                        directory,
                        provider_settings,
                    )
                    result["repeat"] = repeat + 1
                    results.append(result)
                    print(
                        f"{policy:12} {fixture:14} verified={result['verified_success']} {result['wall_seconds']}s",
                        flush=True,
                    )
    summary = {
        policy: {
            "verified_successes": sum(
                r["verified_success"] for r in results if r["policy"] == policy
            ),
            "tasks": sum(r["policy"] == policy for r in results),
            "mean_wall_seconds": round(
                statistics.mean(
                    r["wall_seconds"] for r in results if r["policy"] == policy
                ),
                3,
            ),
        }
        for policy in args.policies
    }
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "mode": args.mode,
                "evidence_note": "Scripted fixture oracle with real isolated validation. Not evidence of model quality, routing savings, or autonomous performance."
                if args.mode == "scripted"
                else "Live provider execution with independent isolated validation",
                "repeats": args.repeats,
                "summary": summary,
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )
    if not all(r["verified_success"] for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
