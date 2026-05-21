# Notebooks

Offline / training-time Jupyter notebooks. These are **not** loaded by the running app — they produce the on-disk model bundles in [`bundles/`](../bundles) that the runtime then memory-maps. See [`docs/architecture.md`](../docs/architecture.md) for how the runtime consumes those bundles.

| Notebook | Trained model(s) | Output bundle |
|---|---|---|
| [`bgg_phase1_trevor_v2_2_fixed.ipynb`](bgg_phase1_trevor_v2_2_fixed.ipynb) | Two-tower neural network (also: Bayesian popularity baseline, TF-IDF content-based) | [`bundles/bgg-two-tower-v1/`](../bundles/bgg-two-tower-v1) |

## `bgg_phase1_trevor_v2_2_fixed.ipynb` — Phase 1 training notebook

Source of the production two-tower model currently shipped in [`bundles/bgg-two-tower-v1/`](../bundles/bgg-two-tower-v1) (the bundle pinned by `MODEL_VERSION` in production CI). Implements and benchmarks three approaches against a shared evaluation harness:

1. **Baseline** — Bayesian-weighted popularity.
2. **Basic** — Content-based filtering with TF-IDF over game features.
3. **Advanced** — Two-tower neural network (the one we actually ship).

**Dataset.** [BoardGameGeek Reviews on Kaggle](https://www.kaggle.com/datasets/jvanelteren/boardgamegeek-reviews) (`jvanelteren/boardgamegeek-reviews`).

**Evaluation.** Leave-one-out per user (random, fixed seed; the reviews CSV has no timestamps). Metrics: RMSE (rating prediction, full test set), Recall@10 and NDCG@10 (ranking on a 10K-user subsample, 99 negatives per positive). All three models share the same split and harness so results are directly comparable.

**Runtime.** Designed for Google Colab with a T4 (or better) GPU — `!pip install` cells, `drive.mount`, and CUDA detection are all wired in. CPU training is technically supported but takes hours.

### How the notebook outputs map to the runtime bundle

The notebook exports a set of files that the runtime loads from `bundles/bgg-two-tower-v1/`. Only the first two are read on every request; the rest are bundle provenance.

| Notebook export | Bundle file | Read at runtime? |
|---|---|---|
| Per-game embedding matrix from the trained item tower | `item_embeddings.npy` | Yes — memory-mapped by [`TwoTowerRecommender.load`](../app/recommenders/two_tower.py) |
| Games metadata (title, BGG id, categories, mechanics, complexity, popularity) | `games_meta.parquet` | Yes — read into the recommender |
| Saved Torch model weights | `two_tower.pt` | No — bundle provenance only |
| Curated category list | `categories.json` | Yes (optional) — read by [`load_category_options`](../app/services/bundle_taxonomy.py) when present |
| Label encoders / id maps | `game_enc.pkl`, `encoders.pkl` | No — needed only if you re-export the bundle |
| Onboarding game subset | `onboarding_games.parquet` | No — historical; runtime picks seed games via [`pick_seed_game_indices`](../app/services/seed_games.py) |

Bundle metadata lives in [`bundles/bgg-two-tower-v1/manifest.json`](../bundles/bgg-two-tower-v1/manifest.json): `model_type`, `version`, `schema_version`, `trained_at`. The registry checks `schema_version` against [`CONTEXT_SCHEMA_VERSION`](../app/recommenders/base.py) before loading.

### Retraining / promoting a new bundle

1. Open the notebook in Colab (Runtime → Change runtime type → T4 GPU) and run all cells.
2. Download the exported artifacts into a new `bundles/<new-version>/` directory locally — at minimum `item_embeddings.npy`, `games_meta.parquet`, and a `manifest.json` with the new version string and `schema_version: 1`.
3. The `.npy` and `.parquet` files are tracked with Git LFS (see [`.gitattributes`](../.gitattributes)); make sure `git lfs install` has run once before you commit them.
4. Set `MODEL_VERSION=<new-version>` in the prod env and redeploy. On the next `/home` visit every user's cached embedding is recomputed automatically because `UserEmbedding.model_version` will no longer match (see [`get_or_refit_user_embedding`](../app/services/embeddings.py)).
