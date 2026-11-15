# Delivery verification

Dispatch is implemented and demonstrable in the cloud workspace at `/workspace/forgeops`. The source repository is published at https://github.com/alags21/dispatch. Live-provider validation still requires credentials. PROGRESS.md contains the full acceptance checklist.

## Implemented system

FastAPI/Pydantic/SQLAlchemy with SQLite and Alembic; a database-backed serial worker and eleven-state deterministic workflow; planner, engineer, security reviewer, tester and verifier roles; scoped source tools; restricted Docker execution; Bandit and optional Semgrep gates; versioned approvals and bounded repairs; configurable model routing and stage context; a provider-agnostic interface with OpenAI-compatible structured tools; persistent usage, findings, tests, diffs and reports; Next.js/TypeScript/Tailwind dashboard; independent fixtures and benchmark runner; Compose and GitHub Actions.

## Verified results

- 36 backend tests passed, including actual Docker repair, timeout/read-only behavior, scanner suppression resistance and Semgrep repair.
- Production frontend build and TypeScript checks passed on Next.js 16.4.6, React 19.3.1 and Node 24.22.1.
- Browser suite passed with actual API data, workflow creation, both repairs, evidence views, patch download and mobile layout. It also passed against the Docker Compose services.
- Host and container startup succeeded. Both application Docker images and both sandbox variants built successfully.
- Alembic upgrade/downgrade/re-upgrade passed on a fresh SQLite database.
- 15/15 scripted policy/fixture benchmark cases passed independent acceptance tests. See benchmarks/report.json and benchmarks/REPORT.md for measured timings and methodology. These do not measure real model performance.
- The demo passed with Bandit alone and with Bandit plus Semgrep, producing three patch versions and two bounded repairs before review readiness.
- Actionlint validated CI configuration. Compose configuration and Ruff critical checks passed. npm audit reported zero known vulnerabilities.
- One upstream deprecation warning occurs in the backend test client; it does not fail tests. Remote GitHub Actions execution was not performed.

## Startup

Follow README.md for full commands. Create a Python virtual environment, install `-c backend/requirements.lock -e './backend[test]'`, prepare `demo/prepare.py`, and build `backend/sandbox.Dockerfile`. From backend run `alembic upgrade head` and Uvicorn on port 8010. From frontend run `npm ci && npm run build && npm run start`. Open http://localhost:3000; API docs are at http://localhost:8010/docs. Execute `.venv/bin/python demo/run.py` from the repository root to reproduce the scripted HTTP demo.

Docker startup: build the sandbox image, then `docker compose up --build`. Runtime paths are deliberately identical on host and trusted backend for sibling Docker bind mounts. The trusted backend holds Docker socket access; agent execution containers do not.

## Cloud certificate handling used for verification

The cloud environment's HTTPS proxy certificate was not present in base images. Verification used temporary copies of Dockerfiles under `/workspace/work`, with a BuildKit secret mounted only during dependency-install RUN instructions:

```
--mount=type=secret,id=proxy_ca,target=/run/proxy-ca.pem,required=true
```

Python installs used `PIP_CERT=/run/proxy-ca.pem`; Node installs used `NODE_EXTRA_CA_CERTS=/run/proxy-ca.pem`. Builds supplied `--secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt`. TLS verification stayed enabled. The certificate and session-only Dockerfiles are not committed. Standard Dockerfiles work on networks with ordinary trusted public CAs.

## Limits and remaining work

Real model credentials are unavailable, so no live-provider run, live benchmark or routing savings claim is made. Configure a current tool/JSON-capable OpenAI-compatible provider and actual tier prices, then validate it.

The owner created `alags21/dispatch`; the project is now pushed to its main branch. The dashboard, browser title, UI initials, patch filenames, README and API documentation title use Dispatch. Internal configuration names retain compatibility. The renamed production build, browser workflow and API tests passed.

The application is a single-operator development MVP, not a hardened multitenant service. Docker isolation shares a kernel. No automatic cloning, dependency installation, code merge or deployment occurs. Recovery preserves queued jobs but fails interrupted active executions safely. Security scanners and generated tests are not complete proofs; review remains human-owned.
