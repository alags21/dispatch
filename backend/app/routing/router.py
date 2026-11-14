from dataclasses import dataclass

TIERS = ["small", "medium", "large"]


@dataclass
class Features:
    stage: str
    complexity: int = 1
    affected_files: int = 1
    repository_files: int = 1
    security_critical: bool = False
    context_tokens: int = 0
    failures: int = 0
    failure_class: str | None = None
    remaining_budget: float = 1.0


@dataclass
class Decision:
    tier: str
    reason: str


def route(policy: str, f: Features, security_minimum: str = "medium") -> Decision:
    if f.remaining_budget <= 0:
        raise ValueError("Model budget exhausted")
    if policy not in {"small_only", "large_only", "adaptive"}:
        raise ValueError("Unknown routing policy")
    tier, reasons = 0, [f"stage={f.stage}"]
    if policy == "large_only":
        tier, reasons = 2, ["large_only benchmark policy"]
    elif policy == "small_only":
        reasons = ["small_only benchmark policy"]
    else:
        if f.stage in {"engineer", "verifier", "planner"}:
            tier = 1
            reasons.append("structured engineering reasoning")
        if f.complexity >= 3 or f.affected_files > 4 or f.context_tokens > 6000 or f.repository_files > 500:
            tier = 2
            reasons.append("complexity/files/context/repository size")
        if f.failures and f.failure_class in {"test_failure", "security_failure", "invalid_output"}:
            tier = min(2, tier + f.failures)
            reasons.append("actionable failure escalation")
        if f.remaining_budget < 0.05 and not f.security_critical:
            tier = min(tier, 1)
            reasons.append("budget conservation")
    if f.security_critical:
        tier = max(tier, TIERS.index(security_minimum))
        reasons.append(f"security floor={security_minimum}")
    return Decision(TIERS[tier], "; ".join(reasons))
