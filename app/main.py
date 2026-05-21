"""FastAPI entry: static, Jinja SSR, SessionMiddleware, model registry warmup — §3 + §5.7."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse
from starlette.templating import Jinja2Templates

from app.api import auth_routes, home_routes, onboarding_routes
from app.auth.cookies import clear_auth_cookies
from app.auth.deps import ProfileUsernameUnavailableError
from app.config import settings
from app.recommenders import popularity, two_tower  # noqa: F401 — @register side effects
from app.recommenders.registry import registry

_PKG = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_PKG / "templates"))


def static_url(path: str) -> str:
    """Versioned static URL — appends ?v=<mtime> so browsers refetch when assets change."""
    full = _PKG / "static" / path.lstrip("/")
    try:
        mtime = int(full.stat().st_mtime)
    except OSError:
        mtime = 0
    return f"/static/{path.lstrip('/')}?v={mtime}"


templates.env.globals["static_url"] = static_url


@asynccontextmanager
async def lifespan(app: FastAPI):
    registry.load_active()
    app.state.templates = templates
    yield


app = FastAPI(title="BGG Rec Sys Phase 1", lifespan=lifespan)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SESSION_SECRET or "unset",
    session_cookie="bgg_session",
    same_site="lax",
    https_only=settings.SECURE_COOKIES,
)


@app.exception_handler(HTTPException)
async def http_exc_redirect_html(request: Request, exc: HTTPException):  # noqa: ARG001
    """303 from auth deps yields a redirect response instead of JSON (SSR)."""
    if exc.status_code in (302, 303, 307, 308) and exc.headers:
        loc = exc.headers.get("location")
        if loc:
            return RedirectResponse(url=str(loc), status_code=exc.status_code)
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=dict(exc.headers or {}))


@app.exception_handler(RequestValidationError)
async def validation_json(request: Request, exc: RequestValidationError):  # noqa: ARG001
    return JSONResponse({"detail": exc.errors()}, status_code=422)


@app.exception_handler(ProfileUsernameUnavailableError)
async def profile_username_unavailable(request: Request, exc: ProfileUsernameUnavailableError):  # noqa: ARG001
    """Auth metadata username clashes with another row in `profiles`; clear cookies and explain on login."""
    resp = RedirectResponse(
        url="/login?error=username_conflict",
        status_code=303,
    )
    clear_auth_cookies(resp)
    return resp


app.mount("/static", StaticFiles(directory=str(_PKG / "static")), name="static")

app.include_router(auth_routes.router)
app.include_router(onboarding_routes.router)
app.include_router(home_routes.router)


@app.get("/healthz")
async def healthz():
    """Registry readiness + manifest-backed recommender diagnostics."""
    return registry.info()
