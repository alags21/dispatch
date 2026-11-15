import json
import os
from pathlib import Path
import tempfile
import threading
import uuid
from cryptography.fernet import Fernet, InvalidToken
from app.providers.configuration import ProviderSetup, Tier, Credentials

_LOCK = threading.RLock()
FIELDS = [
    "provider_kind",
    "provider_url",
    "api_key",
    "model_small",
    "model_medium",
    "model_large",
    "pricing_json",
]


class ProviderStore:
    """Instance-local encrypted settings; the encryption key never enters API responses."""

    def __init__(self, settings):
        self.settings = settings
        self.root = settings.runtime_dir.resolve() / "providers"

    def _cipher(self):
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root.chmod(0o700)
        key_path = self.root / "master.key"
        if key_path.is_symlink():
            raise ValueError("Provider key file cannot be a symlink")
        with _LOCK:
            if not key_path.exists():
                fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "wb") as stream:
                    stream.write(Fernet.generate_key())
            key_path.chmod(0o600)
            return Fernet(key_path.read_bytes())

    def _write(self, path, values):
        cipher = self._cipher()
        with tempfile.NamedTemporaryFile(dir=self.root, delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(cipher.encrypt(json.dumps(values).encode()))
                stream.flush()
                os.fsync(stream.fileno())
                os.replace(temporary, path)
                path.chmod(0o600)
            finally:
                temporary.unlink(missing_ok=True)

    def _read(self, path):
        if path.is_symlink():
            raise ValueError("Provider settings cannot be a symlink")
        try:
            return json.loads(self._cipher().decrypt(path.read_bytes()))
        except (InvalidToken, json.JSONDecodeError):
            raise ValueError(
                "Saved provider settings cannot be decrypted; restore the matching master key or reconfigure"
            ) from None

    def effective(self):
        with _LOCK:
            path = self.root / "settings.enc"
            return (
                self.settings.model_copy(update=self._read(path))
                if path.exists()
                else self.settings.model_copy()
            )

    def ready_settings(self):
        with _LOCK:
            current = self.effective()
            if not self.view()["configured"]:
                raise ValueError("Configure your AI provider in Settings before starting a live run")
            return current

    def credential_values(self, body):
        key = body.api_key.get_secret_value().strip() if body.api_key else ""
        if key:
            return key
        current = self.effective()
        if not key:
            if current.provider_kind != body.kind or current.provider_url.rstrip("/") != body.base_url:
                raise ValueError("Enter a new API key when changing provider or endpoint")
            key = current.api_key
        if not key:
            raise ValueError("Enter the provider API key")
        return key

    def save(self, body: ProviderSetup):
        with _LOCK:
            values = body.settings_values(self.credential_values(body))
            self._write(self.root / "settings.enc", values)
        return self.view()

    def reset(self):
        with _LOCK:
            (self.root / "settings.enc").unlink(missing_ok=True)
        return self.view()

    def view(self):
        current = self.effective()
        problems = []
        try:
            Credentials(kind=current.provider_kind, base_url=current.provider_url, api_key=current.api_key)
        except ValueError:
            problems.append("Configure a valid provider endpoint")
        if not current.api_key.strip():
            problems.append("Add an API key")
        try:
            pricing = json.loads(current.pricing_json)
        except ValueError:
            pricing = {}
        if not isinstance(pricing, dict):
            pricing = {}
        tiers = {}
        for tier in ["small", "medium", "large"]:
            model = getattr(current, f"model_{tier}")
            price = pricing.get(model, {})
            if not isinstance(price, dict):
                price = {}
            try:
                valid = Tier(model=model, **price)
                tiers[tier] = valid.model_dump()
            except (ValueError, TypeError):
                tiers[tier] = {
                    "model": model,
                    "input_per_million": price.get("input_per_million"),
                    "output_per_million": price.get("output_per_million"),
                }
                problems.append(f"Configure the {tier} model and its prices")
        return {
            "kind": current.provider_kind,
            "base_url": current.provider_url,
            "key_saved": bool(current.api_key),
            "configured": not problems,
            "problems": problems,
            "source": "saved"
            if (self.root / "settings.enc").exists()
            else "environment"
            if current.api_key
            else "none",
            **tiers,
        }

    def pin_run(self, run_id, settings):
        with _LOCK:
            self._write(
                self.root / f"run-{uuid.UUID(run_id)}.enc", {name: getattr(settings, name) for name in FIELDS}
            )

    def for_run(self, run_id, require_snapshot=False):
        with _LOCK:
            path = self.root / f"run-{uuid.UUID(run_id)}.enc"
            if path.exists():
                return self.settings.model_copy(update=self._read(path))
            if require_snapshot:
                raise ValueError(
                    "Provider snapshot is unavailable; submit a new run after checking provider settings"
                )
            return self.effective()

    def forget_run(self, run_id):
        with _LOCK:
            (self.root / f"run-{uuid.UUID(run_id)}.enc").unlink(missing_ok=True)
