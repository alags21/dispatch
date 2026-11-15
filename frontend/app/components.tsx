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
  SlidersHorizontal,
} from "lucide-react";

export function Shell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  const [access, setAccess] = useState(false);
  const [token, setToken] = useState("");
  return (
    <div className="app">
      <aside>
        <Link className="brand" href="/" aria-label="Dispatch overview">
          <span className="brand-mark">
            <ArrowUpRight size={26} />
          </span>
          Dispatch<span className="version">BETA</span>
        </Link>
        <div className="workspace">
          <GitBranch size={15} />
          <span>Local workspace</span>
        </div>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Main navigation">
          <Link className={path === "/" ? "active" : ""} href="/">
            <LayoutDashboard size={18} />
            Overview
          </Link>
          <Link className={path === "/new" ? "active" : ""} href="/new">
            <Plus size={18} />
            New workflow
          </Link>
          <Link
            className={path === "/settings" ? "active" : ""}
            href="/settings"
          >
            <SlidersHorizontal size={18} />
            AI provider
          </Link>
        </nav>
        <button
          className="settings-button"
          aria-label="Backend access"
          aria-expanded={access}
          onClick={() => setAccess(!access)}
        >
          <KeyRound size={17} />
          Backend access
        </button>
        {access && (
          <form
            className="token-form"
            onSubmit={(e) => {
              e.preventDefault();
              sessionStorage.setItem("forgeops-token", token);
              location.reload();
            }}
          >
            <label htmlFor="token">Dispatch access token</label>
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
            <p>
              Only needed if this Dispatch instance requires an access token.
              Configure model keys under AI provider.
            </p>
          </form>
        )}
        <div className="sidebar-footer">
          <GitBranch size={14} />
          <span>Local instance</span>
          <small>v0.1.0</small>
        </div>
      </aside>
      <div className="main-shell">
        <header>
          <span>
            Workspace <span className="slash">/</span>
            <strong>
              {path === "/"
                ? "Overview"
                : path === "/new"
                  ? "New workflow"
                  : path === "/settings"
                    ? "AI provider"
                    : "Workflow details"}
            </strong>
          </span>
          <span className="header-label">Dispatch / v0.1</span>
        </header>
        <main>{children}</main>
        <footer>
          Dispatch<span>Local engineering workspace</span>
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
      <Boxes size={29} />
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
