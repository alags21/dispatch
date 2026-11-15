"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  KeyRound,
  SlidersHorizontal,
} from "lucide-react";
import { api, money } from "../lib";
import { ErrorBox } from "../components";

type Kind = "openai" | "anthropic";
type TierName = "small" | "medium" | "large";
type Tier = {
  model: string;
  input_per_million: number | null;
  output_per_million: number | null;
};
type Provider = {
  kind: Kind;
  base_url: string;
  key_saved: boolean;
  configured: boolean;
  source: string;
  problems: string[];
} & Record<TierName, Tier>;
type Editor = { model: string; input: string; output: string };
type Model = {
  id: string;
  name: string;
  input_per_million?: number;
  output_per_million?: number;
};
type CheckResult = {
  message: string;
  model: string;
  input_tokens: number | null;
  output_tokens: number | null;
  estimated_cost: number | null;
};
const names: TierName[] = ["small", "medium", "large"];
const blank = (): Editor => ({ model: "", input: "", output: "" });

export default function ProviderSettings() {
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<Provider | null>(null);
  const [kind, setKind] = useState<Kind>("anthropic");
  const [baseUrl, setBaseUrl] = useState("https://api.anthropic.com/v1");
  const [key, setKey] = useState("");
  const [tiers, setTiers] = useState<Record<TierName, Editor>>({
    small: blank(),
    medium: blank(),
    large: blank(),
  });
  const [models, setModels] = useState<Model[]>([]);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [dirty, setDirty] = useState(false);
  const [splitTiers, setSplitTiers] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const matchingKey = Boolean(
    profile?.key_saved &&
      profile.kind === kind &&
      profile.base_url.replace(/\/$/, "") === baseUrl.replace(/\/$/, ""),
  );

  function load(value: Provider) {
    setProfile(value);
    if (value.source !== "none") {
      setKind(value.kind);
      setBaseUrl(value.base_url);
    }
    setTiers(
      Object.fromEntries(
        names.map((name) => [
          name,
          {
            model: value[name].model,
            input: value[name].input_per_million?.toString() ?? "",
            output: value[name].output_per_million?.toString() ?? "",
          },
        ]),
      ) as Record<TierName, Editor>,
    );
    setSplitTiers(
      names.some(
        (name) => JSON.stringify(value[name]) !== JSON.stringify(value.small),
      ),
    );
    setKey("");
    setDirty(false);
  }
  useEffect(() => {
    let alive = true;
    api<Provider>("/provider")
      .then((p) => {
        if (alive) load(p);
      })
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, []);
  function resetModels() {
    setModels([]);
    setTiers({ small: blank(), medium: blank(), large: blank() });
    setSplitTiers(false);
  }
  function edit(name: TierName, field: keyof Editor, value: string) {
    setTiers((current) => {
      const updated = { ...current[name], [field]: value };
      if (field === "model") {
        if (value !== current[name].model) {
          updated.input = "";
          updated.output = "";
        }
        const selected = models.find((m) => m.id === value);
        if (selected?.input_per_million != null)
          updated.input = String(selected.input_per_million);
        if (selected?.output_per_million != null)
          updated.output = String(selected.output_per_million);
      }
      return {
        ...current,
        [name]: updated,
        ...(name === "small" && !splitTiers
          ? { medium: { ...updated }, large: { ...updated } }
          : {}),
      };
    });
    setDirty(true);
    setCheck(null);
  }
  async function discover() {
    setBusy("models");
    setError("");
    setMessage("");
    try {
      const result = await api<{ models: Model[] }>("/provider/models", {
        method: "POST",
        body: JSON.stringify({ kind, base_url: baseUrl, api_key: key || null }),
      });
      setModels(result.models);
      setMessage(
        `${result.models.length} ${result.models.length === 1 ? "model" : "models"} loaded. Choose a model ID below.`,
      );
    } catch (e) {
      setError(
        (e as Error).message + " You can also enter a model ID manually.",
      );
    } finally {
      setBusy(null);
    }
  }
  async function save(event: React.FormEvent) {
    event.preventDefault();
    setBusy("save");
    setError("");
    setMessage("");
    setCheck(null);
    try {
      const body = {
        kind,
        base_url: baseUrl,
        api_key: key || null,
        ...Object.fromEntries(
          names.map((name) => [
            name,
            {
              model: tiers[name].model,
              input_per_million: Number(tiers[name].input),
              output_per_million: Number(tiers[name].output),
            },
          ]),
        ),
      };
      load(
        await api<Provider>("/provider", {
          method: "POST",
          body: JSON.stringify(body),
        }),
      );
      setMessage("Provider saved. New live workflows will use these settings.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function testConnection() {
    setBusy("test");
    setError("");
    setMessage("");
    setCheck(null);
    try {
      setCheck(await api<CheckResult>("/provider/test", { method: "POST" }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  async function reset() {
    setBusy("reset");
    setError("");
    setCheck(null);
    try {
      load(await api<Provider>("/provider/reset", { method: "POST" }));
      setModels([]);
      setMessage(
        "Saved provider removed. Environment settings apply if configured.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>AI provider</h1>
          <p>Connect your account. Choose the models Dispatch works with.</p>
        </div>
        {profile?.configured && (
          <Link className="button" href="/new?mode=live">
            New live workflow
            <ArrowRight size={16} />
          </Link>
        )}
      </div>
      <div className="settings-grid">
        <form className="panel form-panel" onSubmit={save}>
          <div className="settings-status">
            <span
              className={`badge ${profile?.configured && !dirty ? "ready_for_review" : ""}`}
            >
              <i />
              {dirty
                ? "Unsaved changes"
                : profile?.configured
                  ? "Configured"
                  : "Not configured"}
            </span>
            <span>
              {profile?.source === "environment"
                ? "Using environment settings"
                : profile?.source === "saved"
                  ? "Saved on this instance"
                  : "Add a provider to enable live workflows"}
            </span>
          </div>
          {error && <ErrorBox message={error} />}
          {message && (
            <div className="notice" role="status">
              {message}
            </div>
          )}
          {check && (
            <div className="success-box" role="status">
              <Check size={19} />
              <div>
                {check.message}
                <br />
                <small>
                  {check.model} · {check.input_tokens ?? "—"} input /{" "}
                  {check.output_tokens ?? "—"} output tokens · estimated{" "}
                  {money(check.estimated_cost)}
                </small>
              </div>
            </div>
          )}
          <section className="settings-section">
            <h2>
              <KeyRound size={18} />
              Connection
            </h2>
            <label htmlFor="provider-kind">Provider</label>
            <select
              id="provider-kind"
              value={kind}
              disabled={Boolean(busy) || loading}
              onChange={(e) => {
                const value = e.target.value as Kind;
                setKind(value);
                setBaseUrl(
                  value === "anthropic"
                    ? "https://api.anthropic.com/v1"
                    : "https://api.openai.com/v1",
                );
                setKey("");
                resetModels();
                setDirty(true);
                setCheck(null);
              }}
            >
              <option value="anthropic">Anthropic / Claude</option>
              <option value="openai">OpenAI-compatible API</option>
            </select>
            <label htmlFor="provider-url">API base URL</label>
            <input
              id="provider-url"
              type="url"
              value={baseUrl}
              required
              readOnly={kind === "anthropic"}
              disabled={Boolean(busy) || loading}
              onChange={(e) => {
                setBaseUrl(e.target.value);
                setKey("");
                resetModels();
                setDirty(true);
                setCheck(null);
              }}
            />
            <small>
              {kind === "anthropic"
                ? "Connects directly to Anthropic’s native Messages API."
                : "Use your provider’s OpenAI-compatible base URL, including /v1 where required. Local HTTP endpoints are supported."}
            </small>
            <label htmlFor="provider-key" className="key-row">
              API key {matchingKey && <span>Key saved on server</span>}
            </label>
            <input
              id="provider-key"
              type="password"
              autoComplete="new-password"
              value={key}
              required={!matchingKey}
              disabled={Boolean(busy) || loading}
              placeholder={
                matchingKey
                  ? "Leave blank to keep the saved key"
                  : "Paste your provider API key"
              }
              onChange={(e) => {
                setKey(e.target.value);
                setDirty(true);
                setCheck(null);
              }}
            />
            <small>
              {kind === "anthropic"
                ? "Use an Anthropic Console API key. Claude subscriptions and Claude Code login tokens are not API keys."
                : "Use a key issued by the provider at the endpoint above."}{" "}
              Keys stay on the backend and are never returned by the API.
            </small>
            <div className="settings-actions">
              <button
                className="button"
                type="button"
                disabled={Boolean(busy) || (!key && !matchingKey)}
                onClick={discover}
              >
                {busy === "models"
                  ? "Loading models…"
                  : "Load available models"}
              </button>
            </div>
          </section>
          <section className="settings-section">
            <h2>
              <SlidersHorizontal size={18} />
              Model routing
            </h2>
            <p>
              Use one model to start, or choose separate models for routing
              tiers. Enter current USD rates per million tokens to enable cost
              budgets.
            </p>
            <label className="checkbox-label" htmlFor="split-models">
              <input
                id="split-models"
                type="checkbox"
                checked={splitTiers}
                disabled={Boolean(busy) || loading}
                onChange={(e) => {
                  setSplitTiers(e.target.checked);
                  if (!e.target.checked)
                    setTiers((t) => ({
                      ...t,
                      medium: { ...t.small },
                      large: { ...t.small },
                    }));
                  setDirty(true);
                  setCheck(null);
                }}
              />
              Use different models for each tier
            </label>
            <datalist id="provider-models">
              {models.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name}
                </option>
              ))}
            </datalist>
            {(splitTiers ? names : ["small" as TierName]).map((name) => (
              <div className="tier-editor" key={name}>
                <div className="tier-title">
                  {splitTiers ? name : "Model"}
                  <small>
                    {!splitTiers
                      ? "Used by all five agents"
                      : name === "small"
                        ? "Routine tasks"
                        : name === "medium"
                          ? "Standard engineering"
                          : "Complex changes and repairs"}
                  </small>
                </div>
                <label htmlFor={`model-${name}`}>Model ID</label>
                <input
                  id={`model-${name}`}
                  list="provider-models"
                  required
                  value={tiers[name].model}
                  disabled={Boolean(busy) || loading}
                  onChange={(e) => edit(name, "model", e.target.value)}
                  placeholder="Choose or enter a provider model ID"
                />
                <div className="form-row">
                  <div>
                    <label htmlFor={`input-${name}`}>
                      Input / 1M tokens ($)
                    </label>
                    <input
                      id={`input-${name}`}
                      type="number"
                      min="0"
                      step="any"
                      required
                      value={tiers[name].input}
                      disabled={Boolean(busy) || loading}
                      onChange={(e) => edit(name, "input", e.target.value)}
                      placeholder="Current provider rate"
                    />
                  </div>
                  <div>
                    <label htmlFor={`output-${name}`}>
                      Output / 1M tokens ($)
                    </label>
                    <input
                      id={`output-${name}`}
                      type="number"
                      min="0"
                      step="any"
                      required
                      value={tiers[name].output}
                      disabled={Boolean(busy) || loading}
                      onChange={(e) => edit(name, "output", e.target.value)}
                      placeholder="Current provider rate"
                    />
                  </div>
                </div>
                {name === "small" && splitTiers && (
                  <div className="settings-actions">
                    <button
                      className="button"
                      type="button"
                      disabled={
                        Boolean(busy) ||
                        !tiers.small.model ||
                        !tiers.small.input ||
                        !tiers.small.output
                      }
                      onClick={() => {
                        setTiers((t) => ({
                          ...t,
                          medium: { ...t.small },
                          large: { ...t.small },
                        }));
                        setDirty(true);
                        setCheck(null);
                      }}
                    >
                      Use this model for all tiers
                    </button>
                  </div>
                )}
              </div>
            ))}
            <small>
              Rates are estimates you configure. Check your provider’s current
              pricing; zero is valid for a genuinely free local model. Reported
              usage is recorded separately.
            </small>
          </section>
          <div className="form-actions">
            <button
              className="button primary"
              type="submit"
              disabled={Boolean(busy) || loading}
            >
              {busy === "save" ? "Saving…" : "Save provider"}
            </button>
            <button
              className="button"
              type="button"
              disabled={Boolean(busy) || !profile?.configured || dirty}
              onClick={testConnection}
            >
              {busy === "test" ? "Checking…" : "Test connection"}
            </button>
          </div>
          <small>
            Save before testing. The connection test makes one short, billable
            request using your small-tier model. A successful check verifies
            authentication and tool calling; the full workflow is verified by a
            live run.
          </small>
          {profile?.source === "saved" && (
            <div className="settings-actions">
              <button
                className="text-link"
                type="button"
                disabled={Boolean(busy) || loading}
                onClick={reset}
              >
                Remove saved provider
              </button>
            </div>
          )}
        </form>
        <section className="create-help">
          <h2>Bring your own models</h2>
          <p>
            Use your own provider account and API key. Dispatch does not supply
            model credits.
          </p>
          <div className="setup-step">
            <span>01</span>
            <p>Add your API key and load the available models.</p>
          </div>
          <div className="setup-step">
            <span>02</span>
            <p>Choose model IDs and rates, then save the provider.</p>
          </div>
          <div className="setup-step">
            <span>03</span>
            <p>
              Test the connection, then create a live workflow on a small task.
            </p>
          </div>
          <p>
            Saved settings apply to new workflows. Active runs keep the provider
            configuration they started with.
          </p>
          <p>
            {kind === "anthropic" ? (
              <a
                className="text-link"
                href="https://platform.claude.com/docs/en/about-claude/pricing"
                target="_blank"
                rel="noreferrer"
              >
                Anthropic pricing reference <ArrowUpRight size={14} />
              </a>
            ) : (
              "Get current rates from the provider that operates your API endpoint."
            )}
          </p>
        </section>
      </div>
    </>
  );
}
