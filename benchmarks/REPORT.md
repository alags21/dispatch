# Benchmark evidence

Scripted fixture oracle with real isolated validation. Not evidence of model quality, routing savings, or autonomous performance.

Executed one repeat of each of five deterministic fixtures under each policy. Independent evaluator-owned acceptance tests ran in restricted Docker containers after each workflow.

| Policy | Verified tasks | Mean wall time | Real model calls | API usage/cost |
| --- | ---: | ---: | ---: | --- |
| small_only | 5/5 | 12.223s | 0 | None: scripted oracle |
| large_only | 5/5 | 11.525s | 0 | None: scripted oracle |
| adaptive | 5/5 | 12.781s | 0 | None: scripted oracle |

These are actual measured integration results, not model-quality benchmarks. All policies receive known scripted patches. The security minimum tier still applies to security-sensitive tasks under small_only. No price, token count, or quality improvement is inferred. Wall times include Docker startup and were collected in a shared cloud workspace with other verification jobs; they are informational and unsuitable for policy performance conclusions.

Fixtures: multiplication function bug; invalid API request acceptance; missing owner authorization; average of an empty list; health route spanning main.py and a new health.py. Starting source and requirements are in fixtures/<name>; independent tests live in its validation directory and are never included in agent context.

Report fields tests_passed/tests_failed refer to the independent acceptance suite. The workflow also executes existing and generated tests and retains their logs. Scripted input/output tokens and estimated_api_cost are null to distinguish absence of model activity. The model_calls count is zero; agent_invocations records scripted role executions separately.

Reproduce: `.venv/bin/python benchmarks/run.py --repeats 1`. Use `--repeats N` for repeated comparisons or `--policies adaptive` for one policy. Live evaluation requires configured model credentials and prices. It has not been executed in this delivery.

The standalone demo additionally verifies two bounded repairs: a Bandit block on unsafe eval and a failing zero-quantity assertion. Generated tests and patches are reviewable artifacts. Optional Semgrep scanner validation is recorded in the delivery report.
