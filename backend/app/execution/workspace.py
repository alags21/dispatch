import hashlib
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile


class BoundaryError(ValueError):
    pass


def git(repo: Path, *args: str) -> str:
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": "/dev/null",
        "GIT_TERMINAL_PROMPT": "0",
    }
    return subprocess.check_output(
        [
            "git",
            "-c",
            f"safe.directory={repo.resolve()}",
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(repo),
            *args,
        ],
        env=env,
        text=True,
        timeout=15,
        stderr=subprocess.STDOUT,
    )


class Workspace:
    def __init__(self, path: Path):
        self.path = path.resolve()

    @classmethod
    def create(
        cls, repository: str, allowed_root: Path, destination: Path, max_files=2000, max_bytes=10_000_000
    ):
        source = Path(repository).resolve()
        if not source.is_relative_to(allowed_root.resolve()) or not source.is_dir():
            raise BoundaryError(
                "Repository must be a local Git checkout under the configured repository root"
            )
        tracked = git(source, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
        for filename in tracked:
            parts = Path(filename).parts
            if any(
                x in {".ssh", ".aws", ".npmrc", ".pypirc", ".netrc", "credentials"}
                or (x.startswith(".env") and x not in {".env.example", ".env.sample"})
                for x in parts
            ) or filename.endswith((".pem", ".key")):
                raise BoundaryError("Repository snapshot contains a prohibited credential path")
        base = git(source, "rev-parse", "HEAD").strip()
        listing = git(source, "ls-tree", "-rl", "HEAD").splitlines()
        if (
            len(listing) > max_files
            or sum(int(x.split()[3]) for x in listing if x.split()[3].isdigit()) > max_bytes
        ):
            raise BoundaryError("Repository exceeds snapshot limits")
        if destination.exists():
            raise BoundaryError("Workspace already exists")
        destination.mkdir(parents=True)
        archive = destination.parent / (destination.name + ".tar")
        try:
            git(source, "archive", "--format=tar", f"--output={archive.resolve()}", base)
            with tarfile.open(archive) as bundle:
                for entry in bundle.getmembers():
                    if entry.issym() or entry.islnk() or not (entry.isfile() or entry.isdir()):
                        raise BoundaryError("Symlinks and special files are unsupported in agent workspaces")
                    if not (destination / entry.name).resolve().is_relative_to(destination.resolve()):
                        raise BoundaryError("Unsafe archive member")
                bundle.extractall(destination, filter="data")
        except Exception:
            shutil.rmtree(destination, ignore_errors=True)
            raise
        finally:
            archive.unlink(missing_ok=True)
        git(destination, "init", "-b", "workspace")
        git(destination, "add", ".")
        git(
            destination,
            "-c",
            "user.name=ForgeOps",
            "-c",
            "user.email=forgeops@example.invalid",
            "commit",
            "--allow-empty",
            "-m",
            "Isolated baseline",
        )
        for p in destination.rglob("*"):
            if p.is_file():
                p.chmod(0o644)
            elif p.is_dir():
                p.chmod(0o755)
        destination.chmod(0o755)
        return cls(destination), base

    def safe(self, relative: str, writable=False) -> Path:
        p = self.path / relative
        parts = Path(relative).parts
        if Path(relative).is_absolute() or any(
            x.startswith(".") or x in {"..", "__pycache__"} for x in parts
        ):
            raise BoundaryError("Hidden paths, traversal, and credentials are forbidden")
        if any(x.is_symlink() for x in [p, *p.parents] if x.is_relative_to(self.path)):
            raise BoundaryError("Symlinks are forbidden")
        if not p.resolve().is_relative_to(self.path):
            raise BoundaryError("Path escapes workspace")
        if writable and (
            any(x in {"tests", "test", "validation", "generated"} for x in parts)
            or p.name.startswith("test_")
            or p.name in {"conftest.py", "pytest.ini", "pyproject.toml", "setup.cfg"}
        ):
            raise BoundaryError("Engineer cannot modify validation or execution configuration")
        return p

    def files(self):
        return sorted(
            p.relative_to(self.path).as_posix()
            for p in self.path.rglob("*")
            if p.is_file() and not any(x.startswith(".") for x in p.relative_to(self.path).parts)
        )

    def diff(self):
        git(self.path, "add", "--all")
        return git(self.path, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")

    def digest(self):
        return hashlib.sha256(self.diff().encode()).hexdigest()

    def changed(self):
        self.diff()
        return git(self.path, "diff", "--cached", "--name-only", "HEAD").splitlines()

    def cleanup(self):
        shutil.rmtree(self.path, ignore_errors=True)
