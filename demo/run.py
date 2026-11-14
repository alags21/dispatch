"""Exercise the actual HTTP API and worker; backend must already be running."""

import argparse
import json
from pathlib import Path
import time
import httpx

TASK = "Fix quote multiplication; require nonnegative prices and strictly positive quantities (422 otherwise); enforce document ownership (owner 7 only); return 0 for an empty average. Preserve all routes."


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://127.0.0.1:8010")
    p.add_argument("--output", default="demo/evidence.json")
    args = p.parse_args()
    import os

    headers = (
        {"Authorization": "Bearer " + os.environ["FORGEOPS_API_TOKEN"]}
        if os.environ.get("FORGEOPS_API_TOKEN")
        else {}
    )
    with httpx.Client(base_url=args.url, timeout=20, headers=headers) as client:
        configuration = client.get("/api/configuration")
        configuration.raise_for_status()
        response = client.post(
            "/api/runs",
            json={
                "repository": configuration.json()["repository_root"] + "/demo",
                "task": TASK,
                "mode": "scripted",
                "fixture": "demo",
                "max_repairs": 2,
            },
        )
        response.raise_for_status()
        rid = response.json()["id"]
        print(f"Run {rid} · scripted responses + real Docker validation", flush=True)
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            response = client.get(f"/api/runs/{rid}")
            response.raise_for_status()
            detail = response.json()
            if detail["run"]["status"] in {"READY_FOR_REVIEW", "FAILED", "CANCELLED"}:
                break
            time.sleep(0.5)
        events = client.get(f"/api/runs/{rid}/events").json()
        artifacts = client.get(f"/api/runs/{rid}/artifacts").json()
        states = [e["state"] for e in events]
        assert detail["run"]["status"] == "READY_FOR_REVIEW", detail
        assert detail["run"]["retries"] == 2
        assert states.count("REPAIRING") == 2
        assert any(
            a["kind"] == "security_results" and not a["content"]["passed"]
            for a in artifacts
        )
        assert any(
            a["kind"] == "test_results" and not a["content"]["passed"]
            for a in artifacts
        )
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(
                {
                    "evidence_mode": "scripted_agents_real_docker_gates",
                    "detail": detail,
                    "events": events,
                    "artifacts": artifacts,
                },
                indent=2,
            )
            + "\n"
        )
        print(
            f"PASS: two repairs; gates rerun; patch and review report retained. Dashboard: http://localhost:3000/runs/{rid}"
        )


if __name__ == "__main__":
    main()
