import json
from dataclasses import dataclass


# UTF-8 bytes/3 is deliberately conservative for typical source. Providers report actual usage separately.
def tokens(text: str) -> int:
    return (len(text.encode("utf-8")) + 2) // 3


@dataclass
class Context:
    text: str
    estimated_tokens: int
    omitted: list[str]


def build_context(stage: str, essential: dict, optional: list[tuple[str, str]], budget: int) -> Context:
    text = json.dumps({"stage": stage, **essential}, ensure_ascii=False)
    if tokens(text) > budget:
        raise ValueError("Essential requirements/evidence exceed context budget; refusing to truncate them")
    omitted = []
    for name, value in optional:
        chunk = f"\n--- {name} ---\n{value}"
        remaining = (budget - tokens(text)) * 3
        if len(chunk.encode()) <= remaining:
            text += chunk
        else:
            omitted.append(name)
            if remaining > 100:
                text += chunk.encode()[: remaining - 30].decode("utf-8", errors="ignore") + "\n[truncated]"
    return Context(text, tokens(text), omitted)
