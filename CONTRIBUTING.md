# Contributing

Use Python 3.12+, Node.js 22+, and Docker. Follow the README quick start.

Run `FORGEOPS_DOCKER_TESTS=1 .venv/bin/pytest backend/tests -q`, then `cd frontend && npm run typecheck && npm run build`.
The Docker suite tests actual scanner/test repair, timeouts and read-only mounts. Build the optional Semgrep image and set `FORGEOPS_SEMGREP_TESTS=1` to include its scanner suppression/repair check. Pure unit tests use explicit deterministic fixtures and require no model credentials.

Keep agents separate from orchestration decisions. Never let model statements bypass a deterministic gate. Protect original requirements and error evidence when constructing context. Persist failed invocations and usage. Do not add host execution fallbacks.

Add a separate, independently maintained validation case for each benchmark task. Label scripted results clearly. Never commit credentials, runtime databases, or private repository snapshots. Changes should arrive as reviewable patches; merging remains a human action.
