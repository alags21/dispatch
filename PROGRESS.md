# Dispatch implementation progress

- [x] Phase 1: repository, Python/Next.js, Pydantic schemas, SQLAlchemy, Alembic, health, CI
- [x] Phase 2: provider protocol, OpenAI-compatible tool loop, scoped workspace tools, five roles, labeled scripted provider
- [x] Phase 3: explicit state machine, durable worker, bounded repairs, cancellation, safe restart failure, runtime-scoped abandoned-container cleanup
- [x] Phase 4: deterministic adaptive routing, configurable tiers/prices, stage context budgets, invocation usage/cost telemetry
- [x] Phase 5: real Docker checks, Bandit, optional isolated Semgrep, protected validation, patch-bound approvals, final verifier
- [x] Phase 6: dashboard, creation form, live timeline, patch download, generated tests, findings and final reports
- [x] Phase 7: five independent benchmark fixtures; 15/15 scripted comparisons verified in Docker; measured JSON report
- [x] Phase 8 independent checks: backend and browser suites, production build, migrations round trip, both container builds, Compose startup, actionlint, dependency audit, documentation
- [ ] External: validate against a real model provider (credentials unavailable)
- [x] GitHub repository published: https://github.com/alags21/dispatch (main).

## Acceptance checklist

- [x] Backend starts successfully (host Uvicorn and Docker Compose).
- [x] Frontend starts successfully (production standalone server and Docker Compose).
- [x] Database migrations upgrade, downgrade, and re-upgrade in a fresh database.
- [x] A workflow can be created through the UI (Playwright with real backend and containers).
- [x] All five agents execute through the orchestrator.
- [x] Adaptive routing selects configurable tiers with explanations and security floors.
- [x] Context budgets preserve essential requirements and refuse oversized evidence.
- [x] Security checks block unsafe code, including suppression comments, and clear repairs.
- [x] Test failures trigger engineering repair.
- [x] Repair limits and repeated unsuccessful cycles terminate.
- [x] Every role invocation records telemetry and artifacts; scripted usage is explicitly absent.
- [x] Final results include a reviewable diff and downloadable patch.
- [x] Dashboard uses actual API data.
- [x] Five independently evaluated benchmark fixtures exist.
- [x] Deterministic end-to-end demo passes with two repairs (Bandit, and Bandit plus Semgrep).
- [x] Real provider interface and structured tools are contract-tested with httpx mock transport.
- [ ] Real-provider execution verified with actual credentials: blocked, not claimed.
- [x] Automated backend suite passes: 36 tests including real Docker and optional Semgrep.
- [x] Frontend type checking and Next.js 16.4.6 production build pass.
- [x] UI browser flow and mobile width check pass, also under Docker Compose.
- [x] GitHub Actions workflow validates with actionlint; execution on GitHub is not claimed.
- [x] README, architecture, contributing, operations and security documentation are complete.
- [x] Source review excludes credentials, generated repositories, databases and runtime snapshots.
- [x] Limitations are documented; scripted results are distinguished from live model performance.

## Verified evidence

- Backend: `FORGEOPS_DOCKER_TESTS=1 FORGEOPS_SEMGREP_TESTS=1 .venv/bin/pytest backend/tests -q` → **36 passed**, one upstream Starlette/httpx deprecation warning.
- Frontend: `npm run typecheck`, `npm run build`, `CHROMIUM_PATH=/usr/bin/chromium npm run test:e2e` → pass.
- Production services: actual Compose images built and started; browser-created run reached READY_FOR_REVIEW after two repairs.
- Migrations: fresh-database `upgrade head`, `downgrade base`, `upgrade head` → pass.
- Benchmarks: five fixtures × three policies × one repeat → **15/15 independently verified**, scripted agents with real Docker validation.
- Semgrep: separate scanner virtual environment; local rules; no network; unsafe suppressed eval blocked and repaired source cleared; full demo reached READY_FOR_REVIEW.
- Static/config checks: Ruff critical error selection, Compose configuration, actionlint → pass.
- npm audit: **0 known vulnerabilities** after updating Next.js, React and PostCSS.

## External blockers and exact next steps

**GitHub:** The owner created `alags21/dispatch` and granted access. The tested project and Dispatch UI were pushed to its main branch. Repository creation is no longer a blocker. GitHub Actions is configured and runs on pushes; remote CI results should be checked separately from the recorded local verification.

**Live models:** Set FORGEOPS_API_KEY, all three model IDs, current prices, and the compatible endpoint. Then submit a live run and run `benchmarks/run.py --mode live`. Until that happens, transport contract tests establish adapter mechanics only, not provider compatibility or autonomous task quality.

## Operational limits

Single operator and one serial worker; no public hosting or multitenant security. Queued jobs survive restart; interrupted active jobs fail closed and must be resubmitted. Docker shares the host kernel. The tested sandbox supports Python dependencies baked into its image. Costs are configuration-based estimates; transport failures can leave unknown provider billing. Reviewer judgment remains mandatory. See docs/SECURITY.md and docs/OPERATIONS.md.

## Dispatch branding and GitHub publication

- [x] Rename the dashboard, browser title, UI initials, downloaded patches, API documentation title, and README to Dispatch. Internal configuration names retain compatibility.
- [x] Verify the renamed production UI and publish to https://github.com/alags21/dispatch. Frontend type checking/build, the real browser workflow, and API regression checks pass.

## WSL frontend startup hardening

- [x] Set explicit frontend tracing/Turbopack roots and bound Webpack module and loader lookup to the frontend while preserving nested dependency resolution.
- [x] Explain a missing production build before trying to start the standalone server.
- [x] Reproduce the exact failure with Node 24.15.0, an empty ancestor package.json, an unrelated pnpm lockfile, and ancestor node_modules. The fixed production build and standalone HTTP startup pass without modifying the ancestor files.
- [x] Frontend type checking, the build-isolation regression, the full browser workflow, startup error handling, and CI configuration validation pass. The build-isolation regression is included in CI.
