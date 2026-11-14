"""Remove old terminal-run source snapshots while preserving database artifacts."""

import argparse
from datetime import datetime, UTC, timedelta
import shutil
from sqlalchemy import select
from app.config import Settings
from app.database.models import Run
from app.database.session import database
from app.orchestration.states import TERMINAL


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--older-than-hours", type=float, default=24)
    args = parser.parse_args()
    if args.older_than_hours < 0:
        parser.error("age must be nonnegative")
    settings = Settings()
    _, sessions = database(settings.database_url)
    cutoff = datetime.now(UTC) - timedelta(hours=args.older_than_hours)
    root = (settings.runtime_dir / "runs").resolve()
    with sessions() as db:
        for run in db.scalars(select(Run).where(Run.status.in_(TERMINAL))):
            if run.ended_at and datetime.fromisoformat(run.ended_at) < cutoff:
                path = (root / run.id / "workspace").resolve()
                if path.is_relative_to(root) and path.is_dir():
                    shutil.rmtree(path)
                    print(f"Removed snapshot for {run.id}")


if __name__ == "__main__":
    main()
