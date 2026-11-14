import json


def estimated_cost(pricing_json: str, model: str, input_tokens: int | None, output_tokens: int | None):
    table = json.loads(pricing_json)
    price = table.get(model)
    if price is None or input_tokens is None or output_tokens is None:
        return None
    return (
        input_tokens * price["input_per_million"] + output_tokens * price["output_per_million"]
    ) / 1_000_000
