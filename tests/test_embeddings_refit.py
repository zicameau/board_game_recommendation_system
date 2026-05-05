"""Lazy refit when MODEL_VERSION mismatches persisted row — §5.15.5."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import numpy as np
import pytest

from app.config import settings
from app.db.models.onboarding import OnboardingSelection
from app.db.models.user_embedding import UserEmbedding
from app.recommenders.registry import ModelRegistry


def test_get_or_refit_returns_existing_when_versions_match(monkeypatch):
    from app.services import embeddings as emb

    uid = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")

    cached = MagicMock(spec=UserEmbedding)
    cached.model_version = settings.MODEL_VERSION
    cached.embedding = [0.1, 0.2, 0.3]

    db = MagicMock()
    db.get.side_effect = lambda model, pk: cached if model is UserEmbedding and pk == uid else None

    mock_reg = MagicMock(spec=ModelRegistry)

    vec = emb.get_or_refit_user_embedding(uid, db, mock_reg)
    np.testing.assert_allclose(vec, np.asarray(cached.embedding, dtype=np.float32))
    mock_reg.fit_user_embedding.assert_not_called()


def test_get_or_refit_recomputes_when_version_differs(monkeypatch):
    from app.services import embeddings as emb

    uid = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
    monkeypatch.setattr(emb.settings, "MODEL_VERSION", "v-current")

    old = MagicMock(spec=UserEmbedding)
    old.model_version = "legacy"
    old.embedding = [1.0, 1.0, 1.0]

    sel = MagicMock(spec=OnboardingSelection)
    sel.game_ratings = [{"game_idx": 0, "label": "love"}]

    fake_vec = np.array([9.0, 8.0], dtype=np.float32)

    def _get(model, pk):
        if model is UserEmbedding and pk == uid:
            return old
        if model is OnboardingSelection and pk == uid:
            return sel
        return None

    db = MagicMock()
    db.get.side_effect = _get

    reg = MagicMock(spec=ModelRegistry)
    reg.fit_user_embedding.return_value = fake_vec

    out = emb.get_or_refit_user_embedding(uid, db, reg)
    np.testing.assert_allclose(out, fake_vec)
    reg.fit_user_embedding.assert_called_once()

    merged = db.merge.call_args.args[0]
    assert merged.model_version == "v-current"


def test_onboarding_required_raises(monkeypatch):
    from app.services import embeddings as emb

    monkeypatch.setattr(emb.settings, "MODEL_VERSION", "v-current")
    uid = uuid.UUID("cccccccc-dddd-eeee-ffff-0123456789ab")

    def _get(model, pk):  # noqa: ARG001
        return None

    db = MagicMock()
    db.get.side_effect = _get

    reg = MagicMock()

    with pytest.raises(ValueError, match="onboarding_required"):
        emb.get_or_refit_user_embedding(uid, db, reg)
