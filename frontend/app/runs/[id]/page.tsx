"use client";
import { useEffect, useState, use } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Check,
  Clock,
  GitBranch,
  ShieldCheck,
  Download,
  Square,
  X,
} from "lucide-react";
import {
  api,
  Run,
  Invocation,
  Artifact,
  Event,
  terminal,
  money,
  duration,
  date,
} from "../../lib";
import { Badge, ErrorBox, Empty } from "../../components";
export default function Detail({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const [run, setRun] = useState<Run | null>(null),
    [invocations, setInvocations] = useState<Invocation[]>([]),
    [events, setEvents] = useState<Event[]>([]),
    [artifacts, setArtifacts] = useState<Artifact[]>([]),
    [tab, setTab] = useState("timeline"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    const load = () =>
      Promise.all([
        api<{ run: Run; invocations: Invocation[] }>(`/runs/${id}`),
        api<Event[]>(`/runs/${id}/events`),
        api<Artifact[]>(`/runs/${id}/artifacts`),
      ])
        .then(([d, e, a]) => {
          if (alive) {
            setRun(d.run);
            setInvocations(d.invocations);
            setEvents(e);
            setArtifacts(a);
            setError("");
          }
        })
        .catch((e) => alive && setError(e.message));
    load();
    const timer = setInterval(load, 2000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [id]);
  const latest = (kind: string) =>
    artifacts.filter((a) => a.kind === kind).at(-1);
  async function cancel() {
    setBusy(true);
    try {
      await api(`/runs/${id}/cancel`, { method: "POST" });
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function download() {
    const blob = new Blob([latest("patch")?.content.diff || ""], {
      type: "text/x-diff",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `forgeops-${id}.patch`;
    a.click();
    URL.revokeObjectURL(url);
  }
  const security = latest("security_results"),
    tests = latest("test_results"),
    report = latest("final_report");
  return (
    <>
      <Link href="/" className="back">
        <ArrowLeft size={15} />
        All workflows
      </Link>
      {error && <ErrorBox message={error} />}{" "}
      {!run ? (
        <Empty title="Loading workflow" body="Retrieving execution evidence…" />
      ) : (
        <>
          <div className="page-heading">
            <div>
              <div className="eyebrow mono">WORKFLOW {id.slice(0, 8)}</div>
              <h1 className="detail-title">{run.task}</h1>
              <p className="repo-name">
                <GitBranch size={15} />
                {run.repository} <span className="mode">{run.mode}</span>
              </p>
            </div>
            <div className="heading-actions">
              <Badge status={run.status} />
              {!terminal.includes(run.status) && (
                <button disabled={busy} onClick={cancel} className="button">
                  <Square size={13} />
                  Cancel run
                </button>
              )}
            </div>
          </div>
          {run.mode === "scripted" && (
            <div className="notice">
              Scripted fixture demonstration · known agent responses, real
              Docker security scans and test execution. No model API usage.
            </div>
          )}
          {run.outcome && (
            <div
              className={
                run.status === "READY_FOR_REVIEW" ? "success-box" : "notice"
              }
            >
              {run.status === "READY_FOR_REVIEW" && <ShieldCheck size={18} />}{" "}
              {run.outcome}
            </div>
          )}
          <section className="metrics detail-metrics">
            {[
              ["Duration", duration(run)],
              ["Repair iterations", String(run.retries)],
              [
                "Model tokens",
                (run.input_tokens + run.output_tokens).toLocaleString(),
              ],
              [
                "Estimated API cost",
                run.mode === "scripted" ? "No API usage" : money(run.cost),
              ],
            ].map(([k, v]) => (
              <article className="metric" key={k}>
                <div>{k}</div>
                <strong>{v}</strong>
                <small>
                  {k === "Estimated API cost"
                    ? "Pricing is configured, never hardcoded"
                    : k === "Model tokens"
                      ? "Provider usage when available"
                      : k === "Repair iterations"
                        ? `${run.tool_calls} tool calls`
                        : date(run.created_at)}
                </small>
              </article>
            ))}
          </section>
          <div className="detail-tabs tabs">
            {["timeline", "patch", "tests", "security", "report"].map((t) => (
              <button
                key={t}
                onClick={() => setTab(t)}
                className={t === tab ? "selected" : ""}
              >
                {t[0].toUpperCase() + t.slice(1)}
              </button>
            ))}
          </div>
          {tab === "timeline" && (
            <div className="detail-grid">
              <section className="panel timeline-panel">
                <h2>Execution timeline</h2>
                {events.map((e, i) => (
                  <div className="timeline-item" key={e.id}>
                    <span
                      className={`timeline-dot ${e.state === "FAILED" ? "bad" : e.state === "READY_FOR_REVIEW" ? "good" : ""}`}
                    >
                      {e.state === "FAILED" ? (
                        <X size={14} />
                      ) : i === events.length - 1 &&
                        !terminal.includes(run.status) ? (
                        <Clock size={14} />
                      ) : (
                        <Check size={14} />
                      )}
                    </span>
                    <div>
                      <div className="timeline-title">
                        <strong>{e.state.replaceAll("_", " ")}</strong>
                        <time>
                          {new Date(e.timestamp).toLocaleTimeString()}
                        </time>
                      </div>
                      {e.detail.failure_class && (
                        <p>
                          {e.detail.failure_class.replaceAll("_", " ")}
                          {e.detail.attempt
                            ? ` · Repair ${e.detail.attempt}`
                            : ""}
                        </p>
                      )}
                      {e.detail.message && <p>{e.detail.message}</p>}
                    </div>
                  </div>
                ))}
              </section>
              <section className="panel invocation-panel">
                <h2>Agent invocations</h2>
                {invocations.map((v) => (
                  <details key={v.id}>
                    <summary>
                      <span className="agent-role">
                        {v.role}
                        <small>
                          Attempt {v.attempt + 1} · {v.tier}
                        </small>
                      </span>
                      <span className={v.success ? "positive" : "muted"}>
                        {v.success
                          ? "Complete"
                          : v.failure_class || "Executing"}
                      </span>
                    </summary>
                    <div className="invocation-body">
                      <p>{v.routing_reason}</p>
                      <dl>
                        <dt>Model</dt>
                        <dd>{v.model}</dd>
                        <dt>Duration</dt>
                        <dd>{(v.latency_ms / 1000).toFixed(2)}s</dd>
                        <dt>Context estimate</dt>
                        <dd>{v.context_tokens} tokens</dd>
                        <dt>Input / output</dt>
                        <dd>
                          {v.input_tokens ?? "—"} / {v.output_tokens ?? "—"}
                        </dd>
                        <dt>Estimated API cost</dt>
                        <dd>{money(v.cost)}</dd>
                        <dt>Usage evidence</dt>
                        <dd>{v.usage_source}</dd>
                      </dl>
                      <pre>
                        {JSON.stringify(
                          artifacts.find(
                            (a) =>
                              a.content?.invocation_id === v.id &&
                              a.content?.output,
                          )?.content?.output,
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  </details>
                ))}
              </section>
            </div>
          )}
          {tab === "patch" && (
            <section className="panel artifact-panel">
              <div className="panel-heading">
                <div>
                  <h2>Reviewable patch</h2>
                  <p>
                    {latest("patch")?.content.changed_files?.join(" · ") ||
                      "Waiting for implementation"}
                  </p>
                </div>
                <button
                  className="button"
                  disabled={!latest("patch")}
                  onClick={download}
                >
                  <Download size={15} />
                  Download patch
                </button>
              </div>
              <div className="patch-meta mono">
                Base {run.base_commit?.slice(0, 12) || "—"} · Patch{" "}
                {run.patch_hash?.slice(0, 12) || "—"}
              </div>
              <pre className="diff">
                {(latest("patch")?.content.diff || "No patch produced yet.")
                  .split("\n")
                  .map((l: string, i: number) => (
                    <span
                      key={i}
                      className={
                        l.startsWith("+")
                          ? "diff-add"
                          : l.startsWith("-")
                            ? "diff-remove"
                            : l.startsWith("@@")
                              ? "diff-hunk"
                              : ""
                      }
                    >
                      {l + "\n"}
                    </span>
                  ))}
              </pre>
            </section>
          )}
          {tab === "tests" && (
            <section className="panel artifact-panel">
              <div className="panel-heading">
                <h2>Test evidence</h2>
                {tests && (
                  <Badge
                    status={
                      tests.content.passed ? "READY_FOR_REVIEW" : "FAILED"
                    }
                  />
                )}
              </div>
              <pre>
                {tests?.content.stdout || "Tests have not executed yet."}
              </pre>
              <h3 className="artifact-subtitle">
                Generated tests · independently reviewable
              </h3>
              {Object.entries(latest("generated_tests")?.content || {}).map(
                ([name, code]) => (
                  <details key={name}>
                    <summary>{name}</summary>
                    <pre>{String(code)}</pre>
                  </details>
                ),
              )}
            </section>
          )}
          {tab === "security" && (
            <section className="panel artifact-panel">
              <div className="panel-heading">
                <h2>Security findings</h2>
                {security && (
                  <Badge
                    status={
                      security.content.passed ? "READY_FOR_REVIEW" : "FAILED"
                    }
                  />
                )}
              </div>
              {security && !security.content.findings.length ? (
                <Empty
                  title="No blocking findings"
                  body="Review the scan evidence and deployment-specific risks before merging."
                />
              ) : (
                security?.content.findings.map((f: any, i: number) => (
                  <div className="finding" key={i}>
                    <span className="badge failed">{f.severity}</span>
                    <strong>{f.message}</strong>
                    <small>
                      {f.source} ·{" "}
                      {f.verified
                        ? "Verified scanner / policy evidence"
                        : "LLM advisory"}
                    </small>
                    <pre>{f.evidence}</pre>
                    <p>{f.remediation}</p>
                  </div>
                ))
              )}
              {artifacts
                .filter((a) => a.kind === "security_results")
                .map((a) => (
                  <details key={a.id}>
                    <summary>
                      Scan evidence · {a.patch_hash?.slice(0, 12)} ·{" "}
                      {a.content.passed ? "passed" : "blocked"}
                    </summary>
                    <pre>{JSON.stringify(a.content, null, 2)}</pre>
                  </details>
                ))}
            </section>
          )}
          {tab === "report" && (
            <section className="panel artifact-panel">
              <div className="panel-heading">
                <h2>Final verification report</h2>
              </div>
              {report ? (
                <>
                  <div className="report-summary">
                    <ShieldCheck size={23} />
                    <h3>
                      {report.content.recommendation === "review"
                        ? "Recommended for human review"
                        : "Changes require further work"}
                    </h3>
                    <p>{report.content.summary}</p>
                  </div>
                  <pre>{JSON.stringify(report.content, null, 2)}</pre>
                </>
              ) : (
                <Empty
                  title="Verification pending"
                  body="Final verification follows mandatory security and testing gates."
                />
              )}
            </section>
          )}
        </>
      )}
    </>
  );
}
