from app.models.schemas import ImplementationPlan

ROLE = "planner"
OUTPUT_SCHEMA = ImplementationPlan


def validate(payload):
    return OUTPUT_SCHEMA.model_validate(payload)
