from contextlib import asynccontextmanager
import json
import logging
from pathlib import Path
import secrets
import httpx
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.providers.configuration import ProviderSetup, Credentials
from app.providers.store import ProviderStore
from app.providers.service import check_connection, discover_models
from sqlalchemy import select
from app.config import Settings
from app.database.models import Artifact, Event, Invocation, Run, now
from app.database.session import database
from app.execution.workspace import BoundaryError, git
from app.models.schemas import RunCreate, RunView, EventView, ArtifactView, InvocationView
from app.orchestration.engine import Engine
from app.orchestration.states import TERMINAL
from app.orchestration.worker import Worker


class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps(
            {
                "timestamp": now(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "exception": self.formatException(record.exc_info) if record.exc_info else None,
            }
        )


def create_app(settings=None, engine_override=None):
    settings = settings or Settings()
    settings.prepare()
    db_engine, sessions = database(settings.database_url)
    workflow = engine_override or Engine(settings, sessions)
    worker = Worker(workflow)
    providers = ProviderStore(settings)

    @asynccontextmanager
    async def lifespan(app):
        if settings.worker_enabled:
            worker.start()
        yield
        worker.stop()
        db_engine.dispose()

    app = FastAPI(
        title="Dispatch",
        version="0.1.0",
        lifespan=lifespan,
        description="Evidence-driven engineering orchestration. Scripted fixture mode is not live model evidence.",
    )
    app.state.sessions = sessions
    app.state.workflow = workflow
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.allowed_origin],
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )

    def authorize(authorization: str | None = Header(default=None)):
        if settings.api_token and not secrets.compare_digest(
            authorization or "", "Bearer " + settings.api_token
        ):
            raise HTTPException(401, "Valid bearer token required")

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request, exc):
        # Validation errors must never echo a submitted provider key.
        return JSONResponse(
            status_code=422,
            content={
                "detail": [
                    {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]}
                    for error in exc.errors()
                ]
            },
        )

    def provider_action(action):
        try:
            return action()
        except httpx.HTTPStatusError as exc:
            code = exc.response.status_code
            hint = (
                "Check the API key and account permissions"
                if code in {401, 403}
                else "Check the endpoint, model ID, and provider limits"
            )
            raise HTTPException(502, f"Provider returned HTTP {code}. {hint}.") from None
        except httpx.TimeoutException:
            raise HTTPException(504, "Provider request timed out") from None
        except httpx.RequestError:
            raise HTTPException(502, "Unable to reach the provider endpoint") from None
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        except (KeyError, IndexError, TypeError, AttributeError):
            raise HTTPException(502, "Provider returned an unsupported response format") from None
        except OSError:
            raise HTTPException(503, "Provider settings storage is unavailable") from None

    @app.get("/api/provider", dependencies=[Depends(authorize)])
    def provider_configuration():
        return provider_action(providers.view)

    @app.post("/api/provider", dependencies=[Depends(authorize)])
    def save_provider(body: ProviderSetup):
        return provider_action(lambda: providers.save(body))

    @app.post("/api/provider/reset", dependencies=[Depends(authorize)])
    def reset_provider():
        return provider_action(providers.reset)

    @app.post("/api/provider/models", dependencies=[Depends(authorize)])
    def provider_models(body: Credentials):
        return provider_action(
            lambda: {"models": discover_models(body.kind, body.base_url, providers.credential_values(body))}
        )

    @app.post("/api/provider/test", dependencies=[Depends(authorize)])
    def test_provider():
        view = provider_action(providers.view)
        if not view["configured"]:
            raise HTTPException(422, "Save a complete provider configuration before testing")
        return provider_action(lambda: check_connection(providers.ready_settings()))

    def get_run(db, run_id):
        run = db.get(Run, run_id)
        if not run:
            raise HTTPException(404, "Run not found")
        return run

    @app.get("/api/health")
    def health():
        try:
            with db_engine.connect() as connection:
                from sqlalchemy import text, inspect

                connection.execute(text("SELECT 1"))
                ready = inspect(connection).has_table("runs")
        except Exception:
            raise HTTPException(503, "Database unavailable")
        return {
            "status": "ok" if ready else "migration_required",
            "sandbox_available": workflow.sandbox.available(),
            "worker_enabled": settings.worker_enabled,
        }

    @app.post("/api/runs", response_model=RunView, status_code=201, dependencies=[Depends(authorize)])
    def create_run(body: RunCreate):
        source = Path(body.repository).resolve()
        if not source.is_relative_to(settings.repository_root.resolve()) or not source.is_dir():
            raise HTTPException(422, "Repository must exist under configured FORGEOPS_REPOSITORY_ROOT")
        try:
            git(source, "rev-parse", "HEAD")
        except Exception:
            raise HTTPException(422, "Repository must have an accessible Git HEAD commit")
        live_settings = None
        if body.mode == "live":
            try:
                live_settings = providers.ready_settings()
            except ValueError as exc:
                raise HTTPException(422, str(exc)) from None
            except OSError:
                raise HTTPException(503, "Provider settings storage is unavailable") from None
        with sessions() as db:
            run = Run(**{**body.model_dump(), "repository": str(source)})
            db.add(run)
            db.flush()
            db.add(Event(run_id=run.id, state="CREATED", detail={"mode": body.mode}))
            if live_settings:
                provider_action(lambda: providers.pin_run(run.id, live_settings))
                db.add(
                    Artifact(
                        run_id=run.id,
                        kind="provider",
                        content={
                            "kind": live_settings.provider_kind,
                            "base_url": live_settings.provider_url,
                            "models": {
                                t: getattr(live_settings, f"model_{t}") for t in ["small", "medium", "large"]
                            },
                        },
                    )
                )
            try:
                db.commit()
            except Exception:
                providers.forget_run(run.id)
                raise
            return RunView.model_validate(run)

    @app.get("/api/runs", response_model=list[RunView], dependencies=[Depends(authorize)])
    def list_runs(limit: int = 50, offset: int = 0):
        if not 1 <= limit <= 200 or offset < 0:
            raise HTTPException(422, "limit must be 1..200 and offset nonnegative")
        with sessions() as db:
            return [
                RunView.model_validate(r)
                for r in db.scalars(select(Run).order_by(Run.created_at.desc()).limit(limit).offset(offset))
            ]

    @app.get("/api/runs/{run_id}", dependencies=[Depends(authorize)])
    def detail(run_id: str):
        with sessions() as db:
            run = get_run(db, run_id)
            invocations = list(
                db.scalars(select(Invocation).where(Invocation.run_id == run_id).order_by(Invocation.id))
            )
            return {
                "run": RunView.model_validate(run),
                "invocations": [InvocationView.model_validate(x) for x in invocations],
                "cost_by_agent": {
                    role: sum(x.cost or 0 for x in invocations if x.role == role)
                    for role in {x.role for x in invocations}
                },
                "cost_data": "scripted_no_api_usage"
                if run.mode == "scripted"
                else "estimated_from_usage"
                if all(x.cost is not None for x in invocations)
                else "partial_or_missing",
            }

    @app.get("/api/runs/{run_id}/events", response_model=list[EventView], dependencies=[Depends(authorize)])
    def events(run_id: str):
        with sessions() as db:
            get_run(db, run_id)
            return [
                EventView.model_validate(x)
                for x in db.scalars(select(Event).where(Event.run_id == run_id).order_by(Event.id))
            ]

    @app.get(
        "/api/runs/{run_id}/artifacts", response_model=list[ArtifactView], dependencies=[Depends(authorize)]
    )
    def artifacts(run_id: str):
        with sessions() as db:
            get_run(db, run_id)
            return [
                ArtifactView.model_validate(x)
                for x in db.scalars(select(Artifact).where(Artifact.run_id == run_id).order_by(Artifact.id))
            ]

    @app.post("/api/runs/{run_id}/cancel", response_model=RunView, dependencies=[Depends(authorize)])
    def cancel(run_id: str):
        with sessions() as db:
            run = get_run(db, run_id)
            if run.status in TERMINAL:
                raise HTTPException(409, "Run is already terminal")
            run.cancel_requested = True
            db.commit()
            return RunView.model_validate(run)

    @app.get("/api/configuration", dependencies=[Depends(authorize)])
    def configuration():
        return {
            "repository_root": str(settings.repository_root.resolve()),
            "provider": provider_action(providers.view),
        }

    @app.get("/api/models", dependencies=[Depends(authorize)])
    def models():
        current = provider_action(providers.effective)
        return [
            {"tier": t, "model": getattr(current, f"model_{t}") or None} for t in ["small", "medium", "large"]
        ]

    @app.get("/api/policies", dependencies=[Depends(authorize)])
    def policies():
        return [
            {
                "id": "adaptive",
                "description": "Stage, complexity, context, security floor and retry-aware routing",
            },
            {
                "id": "small_only",
                "description": "Small tier benchmark baseline; security floor still applies",
            },
            {"id": "large_only", "description": "Large tier benchmark baseline"},
        ]

    @app.get("/api/metrics", dependencies=[Depends(authorize)])
    def metrics():
        with sessions() as db:
            runs = list(db.scalars(select(Run)))
            finished = [r for r in runs if r.status in TERMINAL]
            return {
                "total_runs": len(runs),
                "completed": sum(r.status == "READY_FOR_REVIEW" for r in runs),
                "active": sum(r.status not in TERMINAL for r in runs),
                "success_rate": sum(r.status == "READY_FOR_REVIEW" for r in finished) / len(finished)
                if finished
                else None,
                "input_tokens": sum(r.input_tokens for r in runs),
                "output_tokens": sum(r.output_tokens for r in runs),
                "estimated_cost": sum(r.cost for r in runs),
                "scripted_runs": sum(r.mode == "scripted" for r in runs),
                "live_runs": sum(r.mode == "live" for r in runs),
            }

    return app


handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.getLogger("forgeops").addHandler(handler)
logging.getLogger("forgeops").setLevel(logging.INFO)
app = create_app()
