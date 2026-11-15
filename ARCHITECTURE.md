# Architecture

## Control plane

FastAPI exposes Pydantic-validated APIs. SQLAlchemy stores runs, events, role invocations and JSON artifacts in SQLite with WAL and foreign keys. Alembic installs the initial schema. `organization_id` is nullable on the run aggregate so future organization scoping can follow foreign keys without moving execution history.

The API commits CREATED jobs immediately. One database-backed worker selects queued runs serially. A runtime-directory file lock prevents competing workers on the same database/runtime. Use one API process; multi-host coordination is out of scope. During startup, interrupted nonterminal runs are failed with explicit evidence; unstarted jobs remain queued. See operations documentation for exact guarantees.

## Deterministic state machine

`orchestration/states.py` declares allowed transitions for all eleven states. Models never choose transitions. Terminal states cannot reopen. Security and tests approve a SHA-256 of the complete staged diff, including added files. Before engineering starts, both approvals are invalidated, including when engineering later fails. Read-only stages rehash after execution. READY_FOR_REVIEW requires both approvals to match the current patch and every planned acceptance criterion to have a positive verifier assessment. A nonempty diff and generated tests are mandatory.

A blocking security finding or test failure produces structured feedback, increments the bounded repair count, and returns through REPAIRING → IMPLEMENTING. Every changed patch must pass security and tests again. Identical unsuccessful patch/failure pairs stop early. The tool count, elapsed runtime and configured API budget are checked throughout. Cancellation is persisted and polled during container execution and between provider operations.

## Agent and provider boundary

Each agent module owns its role and validated output schema. Prompts specify responsibilities. Tool permissions are enforced in code: planner/security/verifier read only; engineer may write ordinary source and run an exact development-check command; tester may create only flat test_*.py files in a separate validation mount. The OpenAI-compatible provider executes a bounded tool-call loop, appends structured tool results and validates final JSON with Pydantic. It records usage immediately after responses, including when a later operation fails.

ScriptedProvider is a fixture oracle, not an artificial substitute claimed as autonomous performance. It uses known file contents and deliberately creates two failures in the demo. Both providers use the same tools, state machine and deterministic gates. FakeSandbox exists only in unit tests; deployed runtime never uses a fake command result.

## Context, routing and cost

Context construction prioritizes original task, plan and recent actionable feedback. The planner receives a map and instructions, engineering gets selected files, security gets patch/code/dependency context and policy, testing gets original criteria and changed interfaces, and verification gets structured validation artifacts and final patch. Context budgets are per role under an overall ceiling; essential requirements and errors are never silently discarded. File chunks are prioritized and omissions are recorded.

Routing uses explicit Features and a deterministic Decision. Security-sensitive tasks enforce a configurable tier floor. Actionable test/security failures can escalate the next attempt; infrastructure errors do not trigger blind escalation. Every invocation stores model, tier, reasoning, context estimate, input/output usage, cost estimate, latency, attempt and failure class. Prices are external configuration. Scripted and missing usage remain distinguishable. Live mode rejects unpriced model tiers and reserves next-call cost conservatively. Billing unknown after network failure remains an explicit limitation.

## Workspace and execution boundary

Workspace creates a Git archive snapshot of the submitted HEAD after validating repository location, size, paths and archive entries, then creates its own baseline Git repository. Original checkout files are never edited. Tool path resolution rejects traversal, symlinks and hidden credential files. The control plane invokes Git with hooks and fsmonitor disabled.

DockerSandbox launches commands with argument arrays, no network, read-only root and mounts, unprivileged UID, no capabilities, no privilege escalation, bounded tmpfs, memory/CPU/PID/output/time limits, and no model credentials or Docker socket. Only pytest, Bandit and Semgrep executables are allowed. Agent command arguments are further constrained by Tools. Image availability is checked; missing isolation is a terminal error with no host execution fallback.

Bandit scanner outputs are parsed into verified findings; scanner errors fail closed. Optional Semgrep uses bundled local rules. LLM findings have their provenance forced to llm/verified=false. Medium and greater findings block. Tests run existing and separately generated cases, retain logs and fail on nonzero exit or no tests. The verifier can reject readiness but cannot override deterministic failures.

## Artifacts, evaluation and UI

Artifacts are append-only records with timestamps and optional patch hashes: plans, tool evidence, engineering summaries, patch versions, security findings/scanner logs, generated tests, test results, final review reports. Generated test files remain under runtime as reviewable evidence. Success/cancelled code snapshots are discarded. Failed snapshots are retained until the operator cleanup command removes old terminal-run workspaces.

The Next.js TypeScript dashboard uses same-origin `/api` rewrites to FastAPI. It polls actual data; it has no seeded metrics. A session-only bearer token supports the optional backend token. All financial displays distinguish scripted usage from estimated live charges. Run detail shows timeline, invocation metadata, patch download, historical scans, generated test source and final report.

The benchmark harness runs each fixture/policy/repeat in a fresh database and disposable source workspace, then executes evaluator-maintained acceptance tests in Docker independently of generated tests. It records verified success, actual test/scanner evidence, calls, available usage, cost, latency and repairs. Scripted routing comparisons test integration, not model quality. CI runs unit/Docker integration checks, migrations, production frontend build, browser flow and scripted benchmark evidence.

## Extension points

Provider protocol supports additional model adapters; routing and pricing are isolated pure modules. A replacement sandbox can implement the same command/result contract. A future distributed scheduler can claim database jobs transactionally without changing agent roles. Organization authorization must be enforced at API access boundaries before adding tenants. Learned routing requires measured live outcomes and a separately validated policy; no learning is claimed in this version.

## Provider onboarding and native Anthropic

The provider settings API validates endpoint, model IDs and finite nonnegative prices before saving. ProviderStore encrypts a single instance profile in private filesystem storage and pins a separate encrypted snapshot for each live job. The API returns only public connection/model metadata. The worker loads the pinned snapshot and uses its provider type, key, models and prices for all invocations. Terminal cleanup removes the job snapshot.

AnthropicProvider implements the native Messages API, translates role tools into input_schema definitions, consumes tool_use content, appends tool_result responses, and uses a submit_result tool for validated final outputs. It shares the same role restrictions, context/budget checks, telemetry callback and deterministic gates as the compatible adapter. Direct OpenAI requests use max_completion_tokens; other compatible endpoints use max_tokens. Both transport protocols are tested with synthetic HTTP responses, including a complete native-format workflow using real Docker validation. Live-provider execution remains unverified without credentials.

The frontend self-hosts IBM Plex Sans/Mono font assets from installed packages, uses dark neutral surfaces and larger type, and has a provider page with a simple single-model default plus optional tiered models. No external font request is required at build or runtime.
