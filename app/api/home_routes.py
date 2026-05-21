"""Authenticated home page and root redirect.

`GET /home` is the personalized recommendations page. It loads (or refits) the user's
embedding via `get_or_refit_user_embedding`, queries the active recommender for top-k
games, and enriches the rows for the template via `build_recommendation_items`.

`GET /` is just the entry point: redirects guests to `/login`, partially-onboarded users
to `/onboarding/welcome`, and finished users to `/home`.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import DependsLogin, DependsProfileOptional
from app.db.models.onboarding import OnboardingSelection
from app.db.session import get_db
from app.recommenders.registry import registry
from app.services.embeddings import (
    exclude_indices_from_selections,
    get_or_refit_user_embedding,
)
from app.services.recommendation_view import build_recommendation_items

router = APIRouter(tags=["home"])


@router.get("/home")
def home(
    request: Request,
    user: DependsLogin,
    db: Session = Depends(get_db),
):
    """Render the personalized recommendations page.

    Gating: if the user hasn't completed onboarding, or hasn't filled selections, or has
    no embedding the recommender can rebuild, redirect back to the wizard. Otherwise
    compute (or pull from cache) the user vector, ask the registry for top-10 games
    excluding ones already rated, and render `home.html`.
    """
    if user.onboarding_completed_at is None:
        return RedirectResponse("/onboarding/welcome", status_code=303)

    sel = db.get(OnboardingSelection, user.id)
    if sel is None:
        return RedirectResponse("/onboarding/welcome", status_code=303)

    try:
        user_emb = get_or_refit_user_embedding(user.id, db, registry)
    except ValueError:
        return RedirectResponse("/onboarding/welcome", status_code=303)

    excl = exclude_indices_from_selections(sel.game_ratings)
    pairs = registry.top_k(user_emb, excl, k=10)
    rec = registry.recommender
    df = getattr(rec, "games_meta", None)
    items = build_recommendation_items(pairs, df, sel)

    info = registry.info()

    return request.app.state.templates.TemplateResponse(
        request,
        "home.html",
        {
            "request": request,
            "user": user,
            "viewer": user,
            "items": items,
            "model_type": info.get("model_type"),
            "model_version": info.get("version"),
        },
    )


@router.get("/")
def index(
    request: Request,
    response: Response,
    profile: DependsProfileOptional,
):
    """Root URL — bounce the visitor to the right place based on session state."""
    if profile is None:
        return RedirectResponse("/login", status_code=303)
    if profile.onboarding_completed_at is None:
        return RedirectResponse("/onboarding/welcome", status_code=303)
    return RedirectResponse("/home", status_code=303)
