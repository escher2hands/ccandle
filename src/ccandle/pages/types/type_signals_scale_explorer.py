"""
Profile the RAW (pre-scaling) type signal vectors, field by field, to decide
on a per-field scaling function.

This expects raw signal vectors - i.e. the output of get_decomposition_vector
BEFORE StandardScaler (or any other scaling) is applied. If you only have the
already-scaled vectors in TABLE_VECTORS, either:
  (a) re-run generate_signal_vectors_in_bulk but store the pre-scaling X
      to a side table / pickle for profiling, or
  (b) point RAW_SOURCE at that pickle/table.

For each field, prints:
  - zero share (% of corpus where this field is exactly 0)
  - min, p25, p50 (median), p75, p95, max
  - mean, std
  - a suggested scaling strategy based on shape heuristics:
      "binary"        -> field is only ever 0/1 (or 0..small int with <=2 distinct vals)
      "small_int"     -> low integer range, low max, few distinct values -> leave as-is
                          or mild scaling, log1p probably unnecessary
      "heavy_tail"    -> max >> p95, long right tail -> log1p recommended
      "ratio_0_1"     -> values bounded in [0, ~1] -> leave as-is
      "mostly_zero"   -> >80% zeros, nonzero values vary -> log1p + p95 scaling
                          to preserve the zero/nonzero distinction
      "constant"      -> zero variance, useless for clustering -> consider dropping

Outputs:
  - field_profile.csv  (one row per field, all stats + recommendation)
  - prints a formatted table to stdout

Run: python3 profile_signal_fields.py
"""

import sqlite3
import numpy as np
import pandas as pd
from ccandle.config.config_db import PATH_DB, TABLE_VECTORS
from ccandle.pages.types.type_signals_defs import SIGNAL_KEYS

# ---- CONFIG --------------------------------------------------------------
FALLBACK_TABLE = TABLE_VECTORS
FALLBACK_COLUMN = "type_signals_vec"

OUT_PATH = "field_profile.csv"

def load_raw_vectors():
    with sqlite3.connect(PATH_DB) as conn:
        rows = conn.execute(
            f"SELECT id, type_signals_vec FROM {TABLE_VECTORS} WHERE type_signals_vec IS NOT NULL"
        ).fetchall()

    page_ids = [row[0] for row in rows]
    X = np.array([np.frombuffer(row[1], dtype=np.float32) for row in rows], dtype=float)
    return page_ids, X


def classify_field(values):
    n = len(values)
    zero_share = float(np.mean(values == 0))
    nonzero = values[values != 0]
    n_distinct = len(np.unique(values))

    if np.std(values) == 0:
        return "constant"

    if n_distinct <= 2 and set(np.unique(values)).issubset({0.0, 1.0}):
        return "binary"

    p95 = np.percentile(values, 95)
    vmax = values.max()

    if zero_share > 0.8:
        return "mostly_zero"

    if n_distinct <= 8 and vmax <= 10:
        return "small_int"

    if vmax > 0 and p95 > 0 and (vmax / max(p95, 1e-9)) > 3:
        return "heavy_tail"

    if vmax <= 1.5 and values.min() >= -0.01:
        return "ratio_0_1"

    return "other"


RECOMMENDATION = {
    "constant":    "drop (zero variance, no discriminative value)",
    "binary":      "leave as-is (already 0/1)",
    "small_int":   "leave as-is, or divide by max if you want a 0-1-ish scale",
    "heavy_tail":  "log1p, then scale by p95",
    "ratio_0_1":   "leave as-is (already bounded)",
    "mostly_zero": "log1p, then scale by p95 (preserves zero as zero)",
    "other":       "inspect manually - scale by p95 (no log) as a default",
}


def recommend_scaling_algo_per_type_signal():
    page_ids, X = load_raw_vectors()
    print(f"Loaded {len(page_ids)} vectors, dim={X.shape[1]}")

    if X.shape[1] != len(SIGNAL_KEYS):
        print(f"WARNING: vector dim ({X.shape[1]}) != len(SIGNAL_KEYS) ({len(SIGNAL_KEYS)})")

    rows = []
    for j, key in enumerate(SIGNAL_KEYS[:X.shape[1]]):
        col = X[:, j]
        shape = classify_field(col)
        rows.append({
            "field": key,
            "shape": shape,
            "recommendation": RECOMMENDATION[shape],
            "zero_share": np.mean(col == 0),
            "n_distinct": len(np.unique(col)),
            "min": col.min(),
            "p25": np.percentile(col, 25),
            "p50": np.percentile(col, 50),
            "p75": np.percentile(col, 75),
            "p95": np.percentile(col, 95),
            "max": col.max(),
            "mean": col.mean(),
            "std": col.std(),
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_PATH, index=False)
    print(f"\nWrote {OUT_PATH}")

    pd.set_option("display.width", 200)
    pd.set_option("display.max_rows", None)
    print("\n" + df.to_string(index=False, float_format=lambda v: f"{v:.3f}"))

    print("\n--- Summary by recommended strategy ---")
    print(df.groupby("recommendation")["field"].apply(list).to_string())

