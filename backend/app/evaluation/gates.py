import json
from app.models.schemas import Finding


def security_gate(workspace, sandbox, check=None, semgrep=False):
    results = []
    findings = []
    python_files = [f for f in workspace.changed() if f.endswith(".py")]
    if python_files:
        result = sandbox.execute(
            workspace.path,
            ["bandit", "-q", "--ignore-nosec", "-f", "json", "-ll", *python_files],
            check=check,
        )
        results.append(result.dump())
        try:
            data = json.loads(result.stdout)
        except ValueError:
            data = {}
        if result.exit_code not in {0, 1} or "results" not in data or data.get("errors"):
            findings.append(
                Finding(
                    severity="high",
                    source="bandit",
                    verified=True,
                    message="Scanner did not complete successfully",
                    evidence=result.stdout,
                    remediation="Resolve scanner or syntax failure before review",
                )
            )
        for item in data.get("results", []):
            findings.append(
                Finding(
                    severity=item["issue_severity"].lower(),
                    source="bandit",
                    verified=True,
                    message=item["issue_text"],
                    evidence=f"{item['filename']}:{item['line_number']} {item['code']}",
                    remediation=item.get("more_info", "Remove unsafe operation"),
                )
            )
    if semgrep and python_files:
        result = sandbox.execute(
            workspace.path,
            [
                "semgrep",
                "scan",
                "--quiet",
                "--jobs=1",
                "--no-git-ignore",
                "--disable-nosem",
                "--config",
                "/opt/forgeops/security.yml",
                "--json",
                "--metrics=off",
                *python_files,
            ],
            check=check,
        )
        results.append(result.dump())
        try:
            data = json.loads(result.stdout)
            if result.exit_code != 0 or data.get("errors"):
                raise ValueError("Semgrep failed")
            for item in data.get("results", []):
                findings.append(
                    Finding(
                        severity="high",
                        source="semgrep",
                        verified=True,
                        message=item["extra"]["message"],
                        evidence=f"{item['path']}:{item['start']['line']}",
                        remediation="Resolve deterministic Semgrep finding",
                    )
                )
        except (ValueError, AssertionError):
            findings.append(
                Finding(
                    severity="high",
                    source="semgrep",
                    verified=True,
                    message="Semgrep unavailable or scan failed",
                    evidence=result.stdout,
                    remediation="Build the optional Semgrep sandbox image or disable optional scanner",
                )
            )
    for filename in workspace.changed():
        if filename.endswith((".pem", ".key")) or any(x in {"tests", ".github"} for x in filename.split("/")):
            findings.append(
                Finding(
                    severity="high",
                    source="policy",
                    verified=True,
                    message="Protected or credential file changed",
                    evidence=filename,
                    remediation="Remove protected file modification",
                )
            )
    return findings, results


def test_gate(workspace, sandbox, validation, check=None):
    paths = []
    if (workspace.path / "tests").is_dir():
        paths.append("tests")
    if list(validation.rglob("test_*.py")):
        paths.append("/validation")
    if not paths:
        return {"passed": False, "exit_code": 5, "stdout": "No validation tests found"}
    result = sandbox.execute(
        workspace.path,
        ["pytest", "-q", "-p", "no:cacheprovider", "--import-mode=importlib", *paths],
        validation,
        check,
    )
    return {"passed": result.exit_code == 0, **result.dump()}
