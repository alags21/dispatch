from app.models.schemas import AgentOutput

ROLE = "verifier"
OUTPUT_SCHEMA = AgentOutput


def validate(payload):
    return OUTPUT_SCHEMA.model_validate(payload)
