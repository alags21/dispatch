from app.models.schemas import State

TERMINAL = {State.READY_FOR_REVIEW, State.FAILED, State.CANCELLED}
TRANSITIONS = {
    State.CREATED: {State.ANALYZING},
    State.ANALYZING: {State.PLANNING},
    State.PLANNING: {State.IMPLEMENTING},
    State.IMPLEMENTING: {State.SECURITY_REVIEW},
    State.SECURITY_REVIEW: {State.TESTING, State.REPAIRING},
    State.TESTING: {State.FINAL_VERIFICATION, State.REPAIRING},
    State.REPAIRING: {State.IMPLEMENTING},
    State.FINAL_VERIFICATION: {State.READY_FOR_REVIEW},
}


def validate_transition(source: str, target: str):
    if source in TERMINAL or (
        target not in {State.FAILED, State.CANCELLED} and target not in TRANSITIONS.get(source, set())
    ):
        raise ValueError(f"Invalid transition: {source} → {target}")


def gates_current(patch: str | None, security: str | None, tests: str | None) -> bool:
    return bool(patch and patch == security == tests)
