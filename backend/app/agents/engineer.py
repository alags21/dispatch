from app.models.schemas import AgentOutput

ROLE = "engineer"
OUTPUT_SCHEMA = AgentOutput


def validate(payload):
    return OUTPUT_SCHEMA.model_validate(payload)
