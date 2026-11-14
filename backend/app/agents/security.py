from app.models.schemas import AgentOutput

ROLE = "security"
OUTPUT_SCHEMA = AgentOutput


def validate(payload):
    return OUTPUT_SCHEMA.model_validate(payload)
