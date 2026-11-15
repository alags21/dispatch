"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Plus,
  GitPullRequest,
  Activity,
  Coins,
  Search,
  ArrowUpRight,
  ShieldCheck,
} from "lucide-react";
import { api, Run, date, money, duration } from "./lib";
import { Badge, Empty, ErrorBox } from "./components";
type Metrics = {
  total_runs: number;
  completed: number;
  active: number;
  success_rate: number | null;
  input_tokens: number;
  output_tokens: number;
  estimated_cost: number;
  scripted_runs: number;
  live_runs: number;
};
export default function Dashboard() {
  const [runs, setRuns] = useState<Run[]>([]),
    [metrics, setMetrics] = useState<Metrics | null>(null),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all"),
    [loading, setLoading] = useState(true);
  useEffect(() => {
    let alive = true;
    const load = () =>
      Promise.all([api<Run[]>("/runs"), api<Metrics>("/metrics")])
        .then(([r, m]) => {
          if (alive) {
            setRuns(r);
            setMetrics(m);
            setError("");
          }
        })
        .catch((e) => alive && setError(e.message))
        .finally(() => alive && setLoading(false));
    load();
    const timer = setInterval(load, 3000);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, []);
  const filtered = runs.filter(
    (r) =>
      (filter === "all" ||
        (filter === "ready"
          ? r.status === "READY_FOR_REVIEW"
          : !["READY_FOR_REVIEW", "FAILED", "CANCELLED"].includes(r.status))) &&
      `${r.task} ${r.repository}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Workspace overview</h1>
          <p>Run tasks, inspect changes, and review results.</p>
        </div>
        <Link className="button primary" href="/new">
          <Plus size={17} />
          New workflow
        </Link>
      </div>
      {error && <ErrorBox message={error} />}
      <section className="metrics">
        {[
          {
            title: "Total workflows",
            value: metrics?.total_runs,
            icon: GitPullRequest,
            note: "Across all routing policies",
          },
          {
            title: "Ready for review",
            value: metrics?.completed,
            icon: ShieldCheck,
            note:
              metrics?.success_rate == null
                ? "No completed runs yet"
                : `${Math.round(metrics.success_rate * 100)}% of terminal runs`,
          },
          {
            title: "Active workflows",
            value: metrics?.active,
            icon: Activity,
            note: "Running or waiting in queue",
          },
          {
            title: "Estimated API cost",
            value: metrics ? money(metrics.estimated_cost) : undefined,
            icon: Coins,
            note: metrics
              ? `${(metrics.input_tokens + metrics.output_tokens).toLocaleString()} model tokens · scripted runs use no API`
              : "Based on provider usage",
          },
        ].map((m) => (
          <article className="metric" key={m.title}>
            <div>
              {m.title}
              <m.icon size={17} />
            </div>
            <strong>{m.value ?? "—"}</strong>
            <small>{m.note}</small>
          </article>
        ))}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <div>
            <h2>
              Recent runs <span className="count">{runs.length}</span>
            </h2>
            <p>Track execution, inspect evidence, and review changes.</p>
          </div>
          <Link className="text-link" href="/new">
            Create workflow <ArrowRight size={15} />
          </Link>
        </div>
        <div className="table-toolbar">
          <div className="tabs">
            {[
              ["all", "All runs"],
              ["active", "Active"],
              ["ready", "Ready for review"],
            ].map(([v, label]) => (
              <button
                key={v}
                className={filter === v ? "selected" : ""}
                onClick={() => setFilter(v)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="search">
            <Search size={15} />
            <input
              placeholder="Search workflows..."
              aria-label="Search workflows"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>WORKFLOW / REPOSITORY</th>
                <th>STATUS</th>
                <th>ROUTING</th>
                <th>DURATION</th>
                <th>API COST</th>
                <th>CREATED</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {filtered.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link className="run-title" href={`/runs/${r.id}`}>
                      {r.task}
                    </Link>
                    <small className="repo-name">
                      {r.repository.split("/").slice(-2).join("/")}{" "}
                      <span className="mode">{r.mode}</span>
                    </small>
                  </td>
                  <td>
                    <Badge status={r.status} />
                  </td>
                  <td>
                    <span className="policy">
                      {r.policy.replaceAll("_", " ")}
                    </span>
                  </td>
                  <td className="mono">{duration(r)}</td>
                  <td
                    className="mono"
                    title={
                      r.mode === "scripted"
                        ? "Scripted demonstration: no API usage"
                        : "Estimated API cost"
                    }
                  >
                    {r.mode === "scripted" ? "—" : money(r.cost)}
                  </td>
                  <td className="muted nowrap">{date(r.created_at)}</td>
                  <td>
                    <Link
                      className="row-arrow"
                      aria-label={`Open workflow ${r.id}`}
                      href={`/runs/${r.id}`}
                    >
                      <ArrowUpRight size={17} />
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!filtered.length && (
          <Empty
            title={loading ? "Loading workflows…" : "No workflows yet"}
            body={
              query
                ? "No workflows match your search."
                : "Create a workflow to plan, implement, and verify a change."
            }
          />
        )}
        <div className="table-footer">
          <span>
            Showing {filtered.length} of the {runs.length} most recent runs
          </span>
          <span>
            <span className="live-dot" /> Updates every 3 seconds
          </span>
        </div>
      </section>
      <div className="workspace-meta">
        <span>
          {metrics
            ? `${metrics.scripted_runs} scripted / ${metrics.live_runs} live runs`
            : ""}
        </span>
        <span>Completed patches require human review.</span>
      </div>
    </>
  );
}
