"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft, ArrowRight, ShieldCheck, GitBranch } from "lucide-react";
import { api, Run } from "../lib";
import { ErrorBox } from "../components";
export default function Create() {
  const router = useRouter();
  const [repository, setRepository] = useState(""),
    [task, setTask] = useState(
      "Fix quote multiplication; require nonnegative prices and strictly positive quantities (422 otherwise); enforce document ownership (owner 7 only); return 0 for an empty average. Preserve all routes.",
    ),
    [mode, setMode] = useState("scripted"),
    [policy, setPolicy] = useState("adaptive"),
    [budget, setBudget] = useState(1),
    [repairs, setRepairs] = useState(2),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [fixture, setFixture] = useState("demo");
  useEffect(() => {
    api<{ repository_root: string }>("/configuration")
      .then((c) => setRepository(`${c.repository_root}/demo`))
      .catch(() => {});
  }, []);
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const run = await api<Run>("/runs", {
        method: "POST",
        body: JSON.stringify({
          repository,
          task,
          mode,
          policy,
          fixture,
          max_budget: budget,
          max_repairs: repairs,
        }),
      });
      router.push(`/runs/${run.id}`);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back" href="/">
        <ArrowLeft size={15} />
        All workflows
      </Link>
      <div className="page-heading">
        <div>
          <div className="eyebrow">START SOMETHING USEFUL</div>
          <h1>New workflow</h1>
          <p>Describe the change. Let the workflow build the evidence.</p>
        </div>
      </div>
      <div className="create-grid">
        <form onSubmit={submit} className="panel form-panel">
          {error && <ErrorBox message={error} />}
          <h2>
            <GitBranch size={19} />
            Engineering task
          </h2>
          <label htmlFor="repo">Repository path</label>
          <input
            id="repo"
            required
            value={repository}
            onChange={(e) => setRepository(e.target.value)}
            placeholder="Absolute path to an allowed local Git repository"
          />
          <small>
            Repository must be inside the backend’s configured repository root.
          </small>
          <label htmlFor="task">What should change?</label>
          <textarea
            id="task"
            required
            minLength={10}
            rows={6}
            value={task}
            onChange={(e) => setTask(e.target.value)}
          />
          <div className="form-row">
            <div>
              <label htmlFor="mode">Execution mode</label>
              <select
                id="mode"
                value={mode}
                onChange={(e) => setMode(e.target.value)}
              >
                <option value="scripted">Scripted fixture demonstration</option>
                <option value="live">Live model execution</option>
              </select>
            </div>
            <div>
              <label htmlFor="policy">Routing policy</label>
              <select
                id="policy"
                value={policy}
                onChange={(e) => setPolicy(e.target.value)}
              >
                <option value="adaptive">Adaptive</option>
                <option value="small_only">
                  Small only (security floor applies)
                </option>
                <option value="large_only">Large only</option>
              </select>
            </div>
          </div>
          {mode === "scripted" && (
            <>
              <label htmlFor="fixture">Scripted fixture</label>
              <select
                id="fixture"
                value={fixture}
                onChange={(e) => setFixture(e.target.value)}
              >
                {[
                  "demo",
                  "function",
                  "validation",
                  "authorization",
                  "edge",
                  "feature",
                ].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
              <small>
                Use the matching prepared fixture repository and task. The
                script uses known patches; it does not solve arbitrary tasks.
              </small>
            </>
          )}
          <div className="form-row">
            <div>
              <label htmlFor="budget">Maximum API budget (USD)</label>
              <input
                id="budget"
                type="number"
                min="0.0001"
                max="100"
                step="0.0001"
                required
                value={budget}
                onChange={(e) => setBudget(Number(e.target.value))}
              />
            </div>
            <div>
              <label htmlFor="repairs">Maximum repairs</label>
              <input
                id="repairs"
                type="number"
                min="0"
                max="5"
                value={repairs}
                onChange={(e) => setRepairs(Number(e.target.value))}
              />
            </div>
          </div>
          <div className="form-actions">
            <Link className="button" href="/">
              Cancel
            </Link>
            <button disabled={busy} className="button primary" type="submit">
              {busy ? "Creating workflow…" : "Start workflow"}
              <ArrowRight size={16} />
            </button>
          </div>
        </form>
        <section className="create-help">
          <ShieldCheck size={28} />
          <h2>Built for review.</h2>
          <p>
            Changes stay in a disposable checkout. Code execution stays inside
            restricted containers.
          </p>
          <ol>
            <li>Plan against your requirements</li>
            <li>Implement an isolated patch</li>
            <li>Check security and run tests</li>
            <li>Repair with actionable feedback</li>
            <li>Verify evidence for human review</li>
          </ol>
          <div className="notice">
            Scripted mode uses reproducible fixture responses and real
            validation commands. Live mode requires configured credentials,
            model IDs, and prices.
          </div>
        </section>
      </div>
    </>
  );
}
