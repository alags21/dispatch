"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  Boxes,
  LayoutDashboard,
  Plus,
  GitBranch,
  KeyRound,
  ArrowUpRight,
} from "lucide-react";
export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [settings, setSettings] = useState(false);
  const [token, setToken] = useState("");
  return (
    <div className="app">
      <aside>
        <Link className="brand" href="/">
          <span className="brand-mark">
            <Boxes size={23} />
          </span>
          Dispatch<span className="version">BETA</span>
        </Link>
        <div className="workspace">
          <span className="workspace-avatar">D</span>
          <div>
            Engineering workspace<small>Personal · MVP</small>
          </div>
          <span className="workspace-dot" />
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav>
          <Link className={path === "/" ? "active" : ""} href="/">
            <LayoutDashboard size={17} />
            Overview
          </Link>
          <Link className={path === "/new" ? "active" : ""} href="/new">
            <Plus size={17} />
            New workflow
          </Link>
        </nav>
        <div className="sidebar-note">
          <GitBranch size={19} />
          <strong>Evidence before approval.</strong>
          <p>
            Every patch passes security and testing gates before human review.
          </p>
          <span>
            NO AUTOMATIC MERGES <ArrowUpRight size={12} />
          </span>
        </div>
        <button
          className="settings-button"
          onClick={() => setSettings(!settings)}
        >
          <KeyRound size={16} />
          API connection
        </button>
        {settings && (
          <form
            className="token-form"
            onSubmit={(e) => {
              e.preventDefault();
              sessionStorage.setItem("forgeops-token", token);
              location.reload();
            }}
          >
            <label htmlFor="token">Backend bearer token</label>
            <input
              id="token"
              type="password"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoComplete="off"
            />
            <button className="button" type="submit">
              Save for this session
            </button>
          </form>
        )}
        <div className="sidebar-footer">
          <span className="avatar">D</span>
          <div>
            Dispatch<small>Local development</small>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header>
          <span>
            Workspace <span className="slash">/</span>{" "}
            <strong>
              {path === "/"
                ? "Overview"
                : path === "/new"
                  ? "New workflow"
                  : "Workflow details"}
            </strong>
          </span>
          <span className="header-label">
            <span /> Deterministic orchestration
          </span>
        </header>
        <main>{children}</main>
        <footer>
          Dispatch <span>Build with intent. Verify with evidence.</span>
          <span>v0.1.0</span>
        </footer>
      </div>
    </div>
  );
}
export function Badge({ status }: { status: string }) {
  return (
    <span className={`badge ${status.toLowerCase()}`}>
      <i />
      {status.replaceAll("_", " ").toLowerCase()}
    </span>
  );
}
export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="empty">
      <Boxes size={30} />
      <h3>{title}</h3>
      <p>{body}</p>
    </div>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return (
    <div className="error" role="alert">
      {message}
    </div>
  );
}
