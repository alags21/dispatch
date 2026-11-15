import json
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator


class Credentials(BaseModel):
    kind: Literal["openai", "anthropic"] = "openai"
    base_url: str = "https://api.openai.com/v1"
    api_key: SecretStr | None = None

    @field_validator("api_key")
    @classmethod
    def valid_key(cls, value):
        if value is None:
            return None
        key = value.get_secret_value().strip()
        if len(key) > 4096 or any(ord(character) < 33 or ord(character) > 126 for character in key):
            raise ValueError("API keys cannot contain whitespace or control characters")
        return SecretStr(key)

    @field_validator("base_url")
    @classmethod
    def valid_url(cls, value):
        value = value.strip().rstrip("/")
        url = urlsplit(value)
        if not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Use a provider base URL without credentials, query parameters, or fragments")
        local = url.hostname in {"localhost", "127.0.0.1", "::1"}
        if url.scheme != "https" and not (local and url.scheme == "http"):
            raise ValueError("Use HTTPS, or HTTP for a local provider")
        return value

    @model_validator(mode="after")
    def native_endpoint(self):
        if self.kind == "anthropic" and self.base_url != "https://api.anthropic.com/v1":
            raise ValueError("Native Anthropic uses https://api.anthropic.com/v1")
        return self


class Tier(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    input_per_million: float = Field(ge=0, allow_inf_nan=False)
    output_per_million: float = Field(ge=0, allow_inf_nan=False)

    @field_validator("model")
    @classmethod
    def model_id(cls, value):
        if not value.strip():
            raise ValueError("Enter a provider model ID")
        return value.strip()


class ProviderSetup(Credentials):
    small: Tier
    medium: Tier
    large: Tier

    @model_validator(mode="after")
    def consistent_prices(self):
        seen = {}
        for name in ["small", "medium", "large"]:
            tier = getattr(self, name)
            price = (tier.input_per_million, tier.output_per_million)
            if tier.model in seen and seen[tier.model] != price:
                raise ValueError("The same model must have the same prices in every tier")
            seen[tier.model] = price
        return self

    def settings_values(self, key):
        return {
            "provider_kind": self.kind,
            "provider_url": self.base_url,
            "api_key": key,
            **{f"model_{t}": getattr(self, t).model for t in ["small", "medium", "large"]},
            "pricing_json": json.dumps(
                {
                    getattr(self, t).model: getattr(self, t).model_dump(exclude={"model"})
                    for t in ["small", "medium", "large"]
                }
            ),
        }
