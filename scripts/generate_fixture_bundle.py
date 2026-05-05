"""Generate minimal model bundle under bundles/popularity-v1-fixture."""

from pathlib import Path

import json
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / "bundles" / "popularity-v1-fixture"


def main() -> None:
    BUNDLE.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    n = 48
    rows = []
    for i in range(n):
        rows.append(
            {
                "game_idx": i,
                "bgg_id": 100000 + i,
                "title": f"Fixture Game {i}",
                "popularity_score": float(10.0 + rng.random() * 3.0),
            }
        )
    df = pd.DataFrame(rows)
    df.to_parquet(BUNDLE / "games_meta.parquet", index=False)
    manifest = {
        "model_type": "popularity",
        "version": "v1.0.0-fixture",
        "schema_version": 1,
        "trained_at": "2026-05-05T00:00:00Z",
        "files": {"games_meta.parquet": {}},
        "trained_by": "fixture",
        "framework": "numpy",
    }
    (BUNDLE / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    meta = {"metrics": {"hit_rate_at_10": 0.0}, "dataset": {"n_games": n}}
    (BUNDLE / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    emb = rng.standard_normal((n, 16)).astype(np.float32)
    np.save(BUNDLE / "item_embeddings.npy", emb)
    tt = dict(manifest)
    tt["model_type"] = "two_tower"
    tt["version"] = "fixture-tt-mini"
    (ROOT / "bundles" / "two-tower-fixture-mini").mkdir(parents=True, exist_ok=True)
    bd = ROOT / "bundles" / "two-tower-fixture-mini"
    (bd / "manifest.json").write_text(json.dumps(tt, indent=2), encoding="utf-8")
    df.to_parquet(bd / "games_meta.parquet", index=False)
    np.save(bd / "item_embeddings.npy", emb)


if __name__ == "__main__":
    main()
    print("Wrote bundles to", BUNDLE)
