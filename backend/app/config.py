from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FORGEOPS_", env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./runtime/forgeops.db"
    runtime_dir: Path = Path("runtime")
    repository_root: Path = Path("../demo/repos")
    sandbox_image: str = "forgeops-sandbox:local"
    worker_enabled: bool = True
    worker_poll_seconds: float = 0.5
    provider_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_small: str = ""
    model_medium: str = ""
    model_large: str = ""
    pricing_json: str = "{}"
    max_output_tokens: int = 3000
    context_budget: int = 12000
    context_budgets_json: str = (
        '{"planner":8000,"engineer":12000,"security":10000,"tester":10000,"verifier":8000}'
    )
    security_minimum_tier: str = "medium"
    api_token: str = ""
    allowed_origin: str = "http://localhost:3000"
    command_timeout: int = 60
    max_repo_files: int = 2000
    max_repo_bytes: int = 10_000_000
    semgrep_enabled: bool = False

    def prepare(self):
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        if self.database_url.startswith("sqlite:///"):
            Path(self.database_url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
