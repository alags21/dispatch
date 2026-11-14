export type Run = {
  id: string;
  task: string;
  repository: string;
  policy: string;
  mode: string;
  status: string;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  retries: number;
  cost: number;
  input_tokens: number;
  output_tokens: number;
  outcome: string | null;
  tool_calls: number;
  base_commit: string | null;
  patch_hash: string | null;
  security_hash: string | null;
  test_hash: string | null;
};
export type Invocation = {
  id: number;
  role: string;
  model: string;
  tier: string;
  routing_reason: string;
  context_tokens: number;
  input_tokens: number | null;
  output_tokens: number | null;
  cost: number | null;
  usage_source: string;
  latency_ms: number;
  attempt: number;
  success: boolean;
  failure_class: string | null;
};
export type Artifact = {
  id: number;
  kind: string;
  patch_hash: string | null;
  created_at: string;
  content: any;
};
export type Event = {
  id: number;
  state: string;
  timestamp: string;
  detail: any;
};
export const terminal = ["READY_FOR_REVIEW", "FAILED", "CANCELLED"];
export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const token =
    typeof window !== "undefined"
      ? sessionStorage.getItem("forgeops-token")
      : null;
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Backend unavailable" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json();
}
export function money(v: number | null) {
  return v === null ? "Unavailable" : `$${v.toFixed(4)}`;
}
export function duration(run: Run) {
  if (!run.started_at) return "Queued";
  const seconds = Math.max(
    0,
    Math.round(
      ((run.ended_at ? new Date(run.ended_at).getTime() : Date.now()) -
        new Date(run.started_at).getTime()) /
        1000,
    ),
  );
  return seconds < 60
    ? `${seconds}s`
    : `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
}
export function date(v: string) {
  return new Date(v).toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
