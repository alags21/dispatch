import importlib.util
from pathlib import Path
import pytest
from app.config import Settings
from app.database.models import Base
from app.database.session import database

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("demo_prepare", ROOT / "demo/prepare.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture(scope="session")
def repositories(tmp_path_factory):
    return module.prepare(tmp_path_factory.mktemp("repos"))


@pytest.fixture
def setup(tmp_path, repositories):
    settings = Settings(
        database_url=f"sqlite:///{tmp_path}/db.sqlite",
        runtime_dir=tmp_path / "runtime",
        repository_root=repositories,
        worker_enabled=False,
    )
    settings.prepare()
    engine, sessions = database(settings.database_url)
    Base.metadata.create_all(engine)
    yield settings, sessions
    engine.dispose()
