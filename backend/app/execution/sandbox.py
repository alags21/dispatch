import os
from pathlib import Path
import subprocess
import uuid
from dataclasses import dataclass, asdict


@dataclass
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    timed_out: bool = False

    def dump(self):
        return asdict(self)


class IsolationUnavailable(RuntimeError):
    pass


class DockerSandbox:
    def __init__(self, image: str, timeout: int = 60, owner: str | None = None):
        self.image, self.timeout, self.owner = image, timeout, owner

    def available(self):
        try:
            subprocess.run(
                ["docker", "image", "inspect", self.image], check=True, capture_output=True, timeout=5
            )
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def cleanup_abandoned(self):
        if not self.owner:
            return
        result = subprocess.run(
            ["docker", "ps", "-aq", "--filter", f"label=forgeops.owner={self.owner}"],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        identifiers = result.stdout.split()
        if identifiers:
            if not all(identifier.isalnum() for identifier in identifiers):
                raise RuntimeError("Unexpected Docker container identifier")
            subprocess.run(["docker", "rm", "-f", *identifiers], capture_output=True, timeout=15, check=True)

    def execute(self, workspace: Path, command: list[str], validation: Path | None = None, check=None):
        if not command or command[0] not in {"pytest", "bandit", "semgrep"}:
            raise PermissionError("Only pytest, bandit, and semgrep may execute inside the sandbox")
        if not self.available():
            raise IsolationUnavailable("Docker sandbox image unavailable; host execution is forbidden")
        name = "forgeops-" + uuid.uuid4().hex
        args = [
            "docker",
            "run",
            "--name",
            name,
            "--network",
            "none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=128",
            "--memory=512m",
            "--cpus=1",
            "--log-driver",
            "none",
            "--user",
            "65534:65534",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=64m",
            "--mount",
            f"type=bind,src={workspace.resolve()},dst=/repo,readonly",
            "--workdir",
            "/repo",
            "-e",
            "PYTHONPATH=/repo" if command[0] == "pytest" else "PYTHONPATH=",
            "-e",
            "PYTHONDONTWRITEBYTECODE=1",
            "-e",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1",
            "-e",
            "HOME=/tmp",
            "-e",
            "SEMGREP_ENABLE_VERSION_CHECK=0",
            "-e",
            "SEMGREP_SETTINGS_FILE=/tmp/semgrep-settings.yml",
        ]
        if validation:
            args += ["--mount", f"type=bind,src={validation.resolve()},dst=/validation,readonly"]
        if self.owner:
            args += ["--label", f"forgeops.owner={self.owner}"]
        args += [self.image, *command]
        import tempfile
        import time

        with tempfile.TemporaryFile() as output:
            process = subprocess.Popen(args, stdout=output, stderr=subprocess.STDOUT)
            started = time.monotonic()
            timed_out = False
            try:
                while process.poll() is None:
                    if check:
                        check()
                    if output.tell() > 2_000_000:
                        return CommandResult(command, 125, "Output limit exceeded")
                    if time.monotonic() - started > self.timeout:
                        timed_out = True
                        break
                    time.sleep(0.05)
                if timed_out:
                    return CommandResult(command, 124, "Execution timeout", True)
                output.seek(0)
                return CommandResult(
                    command, process.returncode, output.read(200_000).decode(errors="replace")
                )
            finally:
                subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=10)
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
