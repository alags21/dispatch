# Execution and trust boundaries

ForgeOps is a single-operator development MVP. Bind it to loopback. Set `FORGEOPS_API_TOKEN` before exposing it through a trusted gateway. It has no multi-user authorization, tenancy enforcement, TLS termination, or rate limiting.

The trusted control plane uses Git and Docker subprocesses with argument arrays, never an agent-provided host shell. Only local repositories below `FORGEOPS_REPOSITORY_ROOT` are accepted. Workspaces are Git archive snapshots with a separate baseline commit; symlinks, traversal, special files, credential paths and oversized repositories are rejected. Uncommitted source changes are excluded. Agent tools reject hidden paths and protect tests and execution configuration from engineer edits.

Agent-modified Python and tests execute as UID 65534 inside read-only containers, with no network, Docker socket, API keys, additional capabilities, or writable repository mount. Containers have CPU, memory, PID, output and time limits. A bounded `/tmp` is writable. Docker or its configured image being unavailable fails the run. Successful and cancelled code copies are removed; DB artifacts and generated tests are retained. Failed copies are retained for debugging and can be removed after reviewing their DB artifacts; see `docs/OPERATIONS.md`.

Docker shares the host kernel and is not a hardened multitenant sandbox. Run the control plane on a dedicated disposable machine for untrusted repositories. Docker Compose mounts the Docker socket into the trusted backend to launch sibling sandboxes; this is a privileged control-plane capability. The socket is never mounted into agent sandboxes. Arbitrary dependency installation and network access in agent containers are intentionally unsupported. Build a reviewed sandbox image for dependencies you need.

Bandit scans changed Python files and blocks medium/high findings or scanner errors. Optional Semgrep uses local rules without network downloads and a separate virtual environment so scanner dependencies cannot alter the application test environment. Scanner commands do not receive the repository on PYTHONPATH. Suppression comments cannot bypass either scanner. The diff policy protects credential/validation files. LLM security findings remain advisory and unverified; medium/high/critical advisories also block conservatively. Static scans are not a complete authorization audit. Independent tests and human review remain necessary.

Generated tests are separate, visible artifacts. Repository test code is untrusted and can be deceptive. A run's review-ready recommendation is not proof that a malicious repository cannot game its own tests. The benchmark runner executes additional evaluator-maintained tests withheld from agent context. Always inspect the diff, tests, logs and final report.

Known credential filenames are blocked; content-based secret discovery is incomplete. Do not submit repositories containing secrets. No workflow pushes, publishes, deploys or merges source code.

## Provider settings and credentials

Provider keys entered in AI provider are sent to the local backend, never stored in browser local/session storage, and cleared from the form after saving. Settings responses return only a key-present flag. Validation errors omit submitted input values. Provider HTTP errors are summarized without returning provider response bodies, and run errors redact the active run key.

Settings and queued-run provider snapshots use authenticated Fernet encryption under runtime/providers with directory mode 0700 and file mode 0600. The master.key file is stored beside the encrypted configuration and is restricted to the backend OS account. This protects accidental exports of isolated ciphertext; it does not protect against someone who controls that account or copies both the key and encrypted settings. Backups must protect the entire runtime directory and retain its matching master key. Agent sandboxes never mount this directory. Per-run snapshots are deleted at terminal completion or interruption recovery.

A blank key field retains the saved key only when provider kind and endpoint are unchanged. Changing endpoint requires explicitly entering a new key. Native Anthropic is restricted to its official Messages API endpoint; compatible custom endpoints require HTTPS except loopback HTTP for local providers. Redirect following is disabled by the HTTP client default. Only the instance operator should access provider settings. Existing optional bearer authentication protects these routes; this remains a single-operator application.

The connection test uses one short generation request with a forced tool call. It is billable separately from workflow run metrics; the UI returns its usage/cost estimate when available. Model discovery normally uses the provider's models endpoint. External model metadata is not proof of a model's ability to complete engineering tasks. Live workflow validation still matters.
