"""Onboarding wizard routes and the destructive `POST /onboarding/reset`.

The wizard is a chain of 7 GET/POST pairs that progressively populate one
`OnboardingSelection` row per user:

    welcome → seed_ratings → categories → mechanics → complexity → play_context →
    player_profile → summary → POST /onboarding/complete

`/onboarding/complete` validates the seed ratings, fits the user embedding via the active
recommender, persists it (with the current `MODEL_VERSION`), stamps
`profiles.onboarding_completed_at`, and redirects to `/home`.

`POST /onboarding/reset` is the inverse: deletes the embedding + selection rows and
clears `onboarding_completed_at` so the user starts the wizard from a blank slate.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.auth.deps import DependsLogin
from app.onboarding_constants import (
    PLAY_CONTEXT_MAIN_OPTIONS,
    PLAY_CONTEXT_OTHER_VALUE,
    PROFILE_TAG_MAX_LEN,
)
from app.config import settings
from app.db.models.onboarding import OnboardingSelection
from app.db.models.user_embedding import UserEmbedding
from app.db.session import get_db
from app.recommenders.registry import registry
from app.services.bundle_taxonomy import (
    load_category_options,
    load_mechanic_options,
    plain_description,
)
from app.services.seed_games import pick_seed_game_indices
from app.services.embeddings import map_game_ratings_to_signed
from app.services.play_context_field import merge_play_context, split_play_context

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


def _games_payload():
    """Build the template-ready list of 10 seed games for the seed_ratings step.

    Deterministic per `MODEL_VERSION` — `pick_seed_game_indices` returns the same indices
    for every user given the same bundle.
    """
    rec = registry.recommender
    df = getattr(rec, "games_meta", None)
    if df is None:
        return []
    rows = []
    for gi in pick_seed_game_indices(df):
        r = df[df["game_idx"] == gi]
        if len(r) == 0:
            continue
        row = r.iloc[0]
        thumb = row.get("thumbnail") or row.get("image") or ""
        title = row.get("title") or row.get("primary") or "Game"
        rows.append(
            {
                "game_idx": int(row["game_idx"]),
                "title": str(title),
                "bgg_id": int(row.get("bgg_id", row.get("id", 0))),
                "thumbnail": str(thumb).strip(),
                "description": plain_description(row.get("description")),
            }
        )
    return rows


def _ensure_selection(db: Session, user_id, model_version: str) -> OnboardingSelection:
    """Return the user's `OnboardingSelection` row, creating an empty one if missing.

    Every wizard GET calls this so each step is robust to the user landing on it directly
    (e.g. via the URL bar) before earlier steps have run.
    """
    row = db.get(OnboardingSelection, user_id)
    if row:
        return row
    row = OnboardingSelection(
        user_id=user_id,
        game_ratings=[],
        model_version=model_version,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/welcome")
def welcome(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    _ = db
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/welcome.html",
        {"request": request, "user": user, "viewer": user},
    )


@router.get("/seed_ratings")
def seed_ratings_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/seed_ratings.html",
        {
            "request": request,
            "user": user,
            "viewer": user,
            "games": _games_payload(),
            "existing": {r["game_idx"]: r["label"] for r in sel.game_ratings},
        },
    )


@router.post("/seed_ratings")
async def seed_ratings_post(
    request: Request,
    user: DependsLogin,
    db: Session = Depends(get_db),
):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()
    ratings = []
    for g in _games_payload():
        key = f"label_{g['game_idx']}"
        label = form.get(key, "never_played")
        ratings.append({"game_idx": int(g["game_idx"]), "label": str(label)})
    sel.game_ratings = ratings
    sel.model_version = settings.MODEL_VERSION
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/categories", status_code=303)


@router.get("/categories")
def categories_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/categories.html",
        {
            "request": request,
            "user": user,
            "viewer": user,
            "liked": ",".join(sel.liked_categories or []),
            "disliked": ",".join(sel.disliked_categories or []),
            "category_options": load_category_options(),
        },
    )


@router.post("/categories")
async def categories_post(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()

    def _split_csv(name: str) -> list[str]:
        raw = form.get(name) or ""
        return [x.strip() for x in str(raw).split(",") if x.strip()]

    sel.liked_categories = _split_csv("liked_categories")
    sel.disliked_categories = _split_csv("disliked_categories")
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/mechanics", status_code=303)


@router.get("/mechanics")
def mechanics_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/mechanics.html",
        {
            "request": request,
            "user": user,
            "viewer": user,
            "liked": ",".join(sel.liked_mechanics or []),
            "disliked": ",".join(sel.disliked_mechanics or []),
            "mechanic_options": load_mechanic_options(),
        },
    )


@router.post("/mechanics")
async def mechanics_post(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()

    def _split_csv(name: str) -> list[str]:
        raw = form.get(name) or ""
        return [x.strip() for x in str(raw).split(",") if x.strip()]

    sel.liked_mechanics = _split_csv("liked_mechanics")
    sel.disliked_mechanics = _split_csv("disliked_mechanics")
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/complexity", status_code=303)


@router.get("/complexity")
def complexity_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/complexity.html",
        {"request": request, "user": user, "viewer": user, "current": sel.complexity_pref},
    )


@router.post("/complexity")
async def complexity_post(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()
    sel.complexity_pref = str(form.get("complexity_pref") or "medium")
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/play_context", status_code=303)


@router.get("/play_context")
def play_ctx_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    preset, detail = split_play_context(sel.play_context)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/play_context.html",
        {
            "request": request,
            "user": user,
            "viewer": user,
            "play_context_options": PLAY_CONTEXT_MAIN_OPTIONS,
            "play_context_preset": preset,
            "play_context_detail": detail,
            "play_context_other_value": PLAY_CONTEXT_OTHER_VALUE,
        },
    )


@router.post("/play_context")
async def play_ctx_post(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()
    sel.play_context = merge_play_context(
        form.get("play_context_preset"),
        form.get("play_context_detail"),
    )
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/player_profile", status_code=303)


@router.get("/player_profile")
def player_prof_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/player_profile.html",
        {"request": request, "user": user, "viewer": user, "current": sel.player_profile or ""},
    )


@router.post("/player_profile")
async def player_prof_post(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    form = await request.form()
    sel.player_profile = str(form.get("player_profile") or "")[:PROFILE_TAG_MAX_LEN]
    db.add(sel)
    db.commit()
    return RedirectResponse("/onboarding/summary", status_code=303)


@router.get("/summary")
def summary_form(request: Request, user: DependsLogin, db: Session = Depends(get_db)):
    sel = _ensure_selection(db, user.id, settings.MODEL_VERSION)
    return request.app.state.templates.TemplateResponse(
        request,
        "onboarding/summary.html",
        {"request": request, "user": user, "viewer": user, "sel": sel},
    )


@router.post("/complete")
def complete_post(
    request: Request,
    user: DependsLogin,
    db: Session = Depends(get_db),
):
    """Finalize onboarding: validate ratings, fit and persist the user embedding, stamp completion.

    Validation order: at least one non-`never_played` rating is required, and the resulting
    signed weight vector must contain at least one positive or negative weight. Both error
    cases redirect back to `/onboarding/seed_ratings` with an `error=` query parameter.

    On success, persists a new `UserEmbedding` with the active `MODEL_VERSION`, sets
    `onboarding_completed_at = now()`, and redirects to `/home`.
    """
    _ = request
    sel = db.get(OnboardingSelection, user.id)
    if sel is None or len(sel.game_ratings) == 0:
        return RedirectResponse("/onboarding/seed_ratings", status_code=303)

    if sum(1 for r in sel.game_ratings if r.get("label") not in {"never_played"}) < 1:
        return RedirectResponse("/onboarding/seed_ratings?error=min_one_rating", status_code=303)

    sel.model_version = settings.MODEL_VERSION

    pos, neg, wts = map_game_ratings_to_signed(sel.game_ratings)
    if not pos and not neg:
        return RedirectResponse("/onboarding/seed_ratings?error=needs_signal", status_code=303)

    vec = registry.fit_user_embedding(pos, neg, wts)
    db.merge(
        UserEmbedding(
            user_id=user.id,
            embedding=vec.tolist(),
            model_version=settings.MODEL_VERSION,
        )
    )

    user.onboarding_completed_at = datetime.now(timezone.utc)
    db.add(user)
    db.add(sel)
    db.commit()
    return RedirectResponse("/home", status_code=303)


@router.post("/reset")
def reset_post(
    user: DependsLogin,
    db: Session = Depends(get_db),
):
    """Hard reset: drop the user's embedding, onboarding selections, and completion timestamp."""
    emb = db.get(UserEmbedding, user.id)
    if emb is not None:
        db.delete(emb)

    sel = db.get(OnboardingSelection, user.id)
    if sel is not None:
        db.delete(sel)

    user.onboarding_completed_at = None
    db.add(user)
    db.commit()
    return RedirectResponse("/onboarding/welcome", status_code=303)
