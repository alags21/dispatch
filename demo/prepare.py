"""Create disposable local Git fixtures; never executes fixture code on the host."""

import argparse
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def prepare(destination=None):
    dest = Path(destination or ROOT / "demo/repos").resolve()
    for source in (ROOT / "benchmarks/fixtures").iterdir():
        if not source.is_dir():
            continue
        repo = dest / source.name
        if (repo / ".git").exists():
            continue
        shutil.copytree(source / "repo", repo, dirs_exist_ok=True)
        for args in [
            ["init", "-b", "main"],
            ["add", "."],
            [
                "-c",
                "user.name=ForgeOps",
                "-c",
                "user.email=demo@example.invalid",
                "commit",
                "-m",
                "Flawed fixture baseline",
            ],
        ]:
            subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repo), *args],
                check=True,
                capture_output=True,
            )
    return dest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination")
    print(prepare(parser.parse_args().destination))
