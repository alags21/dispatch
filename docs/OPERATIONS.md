# Operations

The API hosts a single serial durable worker. Run exactly one Uvicorn process, without `--reload` in production. A filesystem advisory lock prevents two workers in the same runtime directory. SQLite persists jobs, events, invocations and artifacts. CREATED jobs survive restart and are picked up. Previously active jobs are marked FAILED with an interruption event at startup; they are not silently resumed or marked successful. Submit a new run against the immutable source commit to retry. On startup, when Docker is available, the worker removes abandoned sandbox containers labeled for its own runtime directory after obtaining the worker lock. It never removes containers belonging to another runtime. Exactly-once execution is not claimed. Back up the SQLite database with the API stopped or SQLite's backup API.

Cancellation sets a durable flag. It is checked between model operations, during container polling and before final readiness. An in-flight HTTP model request can take up to its 45-second timeout to return. Container commands have their own timeout. A run wall-time limit is enforced at these checkpoints, not by preempting HTTP inside its transport. On graceful shutdown the worker receives a stop signal and the API waits briefly; long active runs can be interrupted on process exit and are failed on restart.

Artifacts include versioned diffs, generated tests, scanner outputs, test logs, role outputs and final reports. Successful/cancelled source snapshots are removed. Failed snapshots are retained at `runtime/runs/<id>/workspace`. After archiving DB artifacts, remove abandoned snapshots using `python -m app.execution.cleanup --older-than-hours 24` from backend. Active and queued jobs are excluded.

Only operator-prepared local Git repositories under the configured root are supported. Clone repositories yourself before submitting. Source checkout files remain unchanged. No remote URL fetching or credential propagation occurs in workflow agents.

Live mode requires API key, all tier model IDs, and prices for all three. Use an OpenAI-compatible chat-completions provider supporting tools and JSON responses. The adapter is contract-tested with httpx mock transport; no real provider run is claimed without credentials. Requests reserve a conservative UTF-8 input bound plus output cap against remaining cost. Reported actual usage updates run totals; missing usage is estimated and labeled. Transport failure before receiving usage may incur unknown provider charges, which cannot be measured here. Treat budget enforcement as best effort for provider billing, not an account spending limit.

Prices are configuration, not fetched market data. Estimated cost is not an invoice. Scripted usage is absent and shown as 'No API usage'. Per-agent summaries and invocation usage sources expose partial/missing data.

To enable Semgrep, build `backend/semgrep.Dockerfile` as a separate sandbox image, set `FORGEOPS_SANDBOX_IMAGE` to it and `FORGEOPS_SEMGREP_ENABLED=true`. Its local Python rules detect eval and shell=True; rules are intentionally small. The default tested image uses Bandit.

## Managing a provider through the dashboard

AI provider supports native Anthropic and OpenAI-compatible endpoints. Saving applies without restarting the backend and affects new runs. Created live jobs have an encrypted private snapshot; changing or removing the active profile does not rewrite queued/active jobs. Public run artifacts record provider kind, endpoint and selected model IDs, never keys. Environment configuration remains an optional fallback, with UI settings taking precedence.

Model IDs are discovered where supported and can be entered manually. Configure actual prices to make budget estimates meaningful. Cache/batch charges and provider invoices may differ from standard configured input/output rates. A successful connection check proves authentication and tool calling for one model; it is not end-to-end quality evidence. Credentials are not available in this development session, so live validation is not claimed.

Profiles live under runtime/providers. Keep the master.key with encrypted settings in secured backups. Do not commit either. If encrypted settings are corrupted, enter a fresh key and save a complete profile; to recover old encrypted snapshots, restore the matching master key. Interrupted jobs fail closed and their private snapshot is removed during recovery.

For the CLI evaluator, `--provider-runtime <instance runtime directory>` loads that instance's saved profile once before creating evaluation workspaces. Without it, benchmark model configuration comes from the environment.
