import os
from pathlib import Path
import pytest
from sqlalchemy import select
from app.database.models import Run, Artifact
from app.execution.sandbox import DockerSandbox
from app.orchestration.engine import Engine
from test_workflow import create

pytestmark = pytest.mark.skipif(
    os.environ.get("FORGEOPS_DOCKER_TESTS") != "1",
    reason="Set FORGEOPS_DOCKER_TESTS=1 for real Docker integration",
)


def test_real_docker_security_test_repair_loop(setup):
    settings, sessions = setup
    assert DockerSandbox(settings.sandbox_image).available()
    rid = create(sessions, settings.repository_root / "demo")
    Engine(settings, sessions).execute(rid)
    with sessions() as db:
        r = db.get(Run, rid)
        assert r.status == "READY_FOR_REVIEW", r.outcome
        assert r.retries == 2 and r.patch_hash == r.security_hash == r.test_hash
        artifacts = list(db.scalars(select(Artifact).where(Artifact.run_id == rid)))
        assert any(
            a.kind == "security_results"
            and any(f["source"] == "bandit" and "insecure" in f["message"] for f in a.content["findings"])
            for a in artifacts
        )
        assert any(a.kind == "test_results" and "1 failed" in a.content["stdout"] for a in artifacts)


def test_timeout_and_read_only_mount(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir(mode=0o755)
    (workspace / "test_timeout.py").write_text("import time\ndef test_timeout(): time.sleep(5)\n")
    (workspace / "test_timeout.py").chmod(0o644)
    workspace.chmod(0o755)
    result = DockerSandbox("forgeops-sandbox:local", timeout=1).execute(
        workspace, ["pytest", "-q", "-p", "no:cacheprovider"]
    )
    assert result.timed_out and result.exit_code == 124
    (workspace / "test_timeout.py").write_text(
        "from pathlib import Path\nimport pytest\ndef test_readonly():\n    with pytest.raises(OSError): Path('/repo/escaped').write_text('bad')\n    assert not Path('/var/run/docker.sock').exists()\n"
    )
    result = DockerSandbox("forgeops-sandbox:local").execute(
        workspace, ["pytest", "-q", "-p", "no:cacheprovider"]
    )
    assert result.exit_code == 0, result.stdout


@pytest.mark.skipif(os.environ.get("FORGEOPS_SEMGREP_TESTS") != "1", reason="Optional Semgrep image required")
def test_scanners_block_suppressed_unsafe_code_and_clear_repair(tmp_path, repositories):
    from app.execution.workspace import Workspace
    from app.evaluation.gates import security_gate

    workspace, _ = Workspace.create(str(repositories / "function"), repositories, tmp_path / "scan-workspace")
    source = workspace.safe("domain.py", writable=True)
    source.write_text(
        'def total(price, quantity):\n    return eval("price * quantity")  # nosec # nosemgrep\n'
    )
    source.chmod(0o644)
    sandbox = DockerSandbox("forgeops-sandbox:semgrep", timeout=30)
    findings, evidence = security_gate(workspace, sandbox, semgrep=True)
    assert {f.source for f in findings} == {"bandit", "semgrep"}, evidence
    assert all(
        "scan failed" not in f.message.lower() and "did not complete" not in f.message for f in findings
    ), evidence
    source.write_text("def total(price, quantity):\n    return price * quantity\n")
    findings, evidence = security_gate(workspace, sandbox, semgrep=True)
    assert not findings, evidence
