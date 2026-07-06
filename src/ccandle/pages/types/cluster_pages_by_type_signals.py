"""
Cluster pages by type-signal embedding vectors and produce inspection artifacts.

Pipeline:
  1. Load vectors (your load_type_signal_vectors)
  2. Normalize (L2) -> cosine-like distance behaves well with euclidean afterwards
  3. UMAP -> reduce to a lower-dim space for clustering (denser, less noisy than raw)
  4. HDBSCAN -> discover natural clusters + noise (-1)
  5. UMAP -> 2D projection for visualization (separate from the clustering embedding)
  6. Output:
       - clusters.csv          (page_id, cluster_id, prob, x, y)
       - cluster_summary.csv   (cluster_id, size, centroid_*  + nearest-page exemplars)
       - cluster_scatter.png   (2D plot colored by cluster)
       - per-cluster sample pids printed for manual inspection

Run: python3 cluster_type_signals.py
"""

import sqlite3
import numpy as np
import pandas as pd
import matplotlib
from ccandle.config.config_db import PATH_DB, TABLE_PAGES

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from sklearn.preprocessing import normalize
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
import hdbscan

from ccandle.pages.types.decompose_page_into_type_signals import load_type_signal_vectors

# ---- CONFIG --------------------------------------------------------------

OUT_DIR = ""  # where csv/png artifacts go

# HDBSCAN params - tune these based on corpus size / desired granularity
MIN_CLUSTER_SIZE = 25                # smallest "real" cluster you'd accept
MIN_SAMPLES = 10                     # higher = more conservative, more noise
CLUSTER_SELECTION_EPSILON = 0.0      # 0 = let HDBSCAN pick; raise to merge nearby clusters

# PCA params for clustering embedding (optional dimensionality reduction
# before HDBSCAN; set to None to skip and cluster on raw normalized vectors)
PCA_CLUSTER_DIM = None                 # None to disable; reasonable for ~5.7K x high-dim vectors

# PCA params for 2D visualization
PCA_VIZ_DIM = 2

# How many sample pids to print per cluster for manual inspection
N_SAMPLES_PER_CLUSTER = 8

RANDOM_STATE = 42

# ---- READABILITY: pull human-readable metadata for inspection ---------------
def load_page_metadata(pids):
    """
    Best-effort lookup of titles for the sampled pids, so cluster
    inspection output is actually readable. Adjust table/column names to
    match your schema. Returns dict page_id -> dict(title=..., url=...).
    Falls back to empty dict if the table/columns don't exist.
    """
    meta = {}
    try:
        with sqlite3.connect(PATH_DB) as conn:
            placeholders = ",".join("?" for _ in pids)
            query = f"SELECT id, title, word_count FROM {TABLE_PAGES} WHERE id IN ({placeholders})"
            for row in conn.execute(query, pids).fetchall():
                meta[row[0]] = {"title": row[1], "word_count": row[2]}
    except sqlite3.OperationalError:
        pass
    return meta


# ---- MAIN -------------------------------------------------------------------
def main():
    print("Loading vectors...")
    page_ids, X = load_type_signal_vectors()
    print(f"Loaded {len(page_ids)} vectors, dim={X.shape[1]}")

    # L2-normalize so euclidean distance in UMAP/HDBSCAN approximates cosine
    X_norm = normalize(X, norm="l2")

    # --- Embedding for clustering (optional PCA reduction) ---
    if PCA_CLUSTER_DIM is not None and PCA_CLUSTER_DIM < X_norm.shape[1]:
        print(f"Running PCA -> {PCA_CLUSTER_DIM}D for clustering embedding...")
        clust_pca = PCA(n_components=PCA_CLUSTER_DIM, random_state=RANDOM_STATE)
        X_clust = clust_pca.fit_transform(X_norm)
        explained = clust_pca.explained_variance_ratio_.sum()
        print(f"  explained variance: {explained:.1%}")
    else:
        print("Clustering on raw normalized vectors (no PCA reduction)...")
        X_clust = X_norm

    # --- HDBSCAN clustering ---
    print("Running HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=MIN_SAMPLES,
        cluster_selection_epsilon=CLUSTER_SELECTION_EPSILON,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    labels = clusterer.fit_predict(X_clust)
    probs = clusterer.probabilities_

    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    print(f"Found {n_clusters} clusters, {n_noise} noise points "
          f"({n_noise / len(labels):.1%} of corpus)")

    if n_clusters >= 2:
        non_noise = labels != -1
        if non_noise.sum() > 1:
            try:
                sil = silhouette_score(X_clust[non_noise], labels[non_noise])
                print(f"Silhouette score (non-noise points): {sil:.3f}")
            except ValueError:
                pass

    # --- 2D embedding purely for visualization ---
    print("Running PCA for 2D visualization...")
    viz_pca = PCA(n_components=PCA_VIZ_DIM, random_state=RANDOM_STATE)
    X_2d = viz_pca.fit_transform(X_norm)
    print(f"  2D explained variance: {viz_pca.explained_variance_ratio_.sum():.1%}")

    # --- Build main dataframe ---
    df = pd.DataFrame({
        "page_id": page_ids,
        "cluster_id": labels,
        "prob": probs,
        "x": X_2d[:, 0],
        "y": X_2d[:, 1],
    })
    df.to_csv(f"{OUT_DIR}/clusters.csv", index=False)
    print(f"Wrote {OUT_DIR}/clusters.csv")

    # --- Cluster size summary ---
    summary = (
        df.groupby("cluster_id")
        .agg(size=("page_id", "count"), mean_prob=("prob", "mean"))
        .sort_values("size", ascending=False)
        .reset_index()
    )
    summary.to_csv(f"{OUT_DIR}/cluster_summary.csv", index=False)
    print(f"Wrote {OUT_DIR}/cluster_summary.csv")
    print("\nCluster sizes:")
    print(summary.to_string(index=False))

    # --- Scatter plot ---
    print("\nPlotting scatter...")
    fig, ax = plt.subplots(figsize=(12, 9))
    unique_labels = sorted(df["cluster_id"].unique())
    cmap = plt.get_cmap("tab20")

    for i, cl in enumerate(unique_labels):
        sub = df[df["cluster_id"] == cl]
        if cl == -1:
            ax.scatter(sub["x"], sub["y"], s=5, c="lightgray", label="noise", alpha=0.4)
        else:
            ax.scatter(sub["x"], sub["y"], s=8, color=cmap(i % 20), label=f"cluster {cl} (n={len(sub)})", alpha=0.7)

    ax.set_title("Type-signal clusters (PCA 2D projection)")
    ax.legend(markerscale=2, fontsize=8, loc="best", ncol=2)
    plt.tight_layout()
    plt.savefig(f"{OUT_DIR}/cluster_scatter.png", dpi=150)
    print(f"Wrote {OUT_DIR}/cluster_scatter.png")

    # --- Per-cluster sample page_ids for manual inspection ---
    print("\n--- Sample pages per cluster (for manual inspection) ---")
    id_to_meta = load_page_metadata(page_ids)

    for cl in summary["cluster_id"]:
        sub = df[df["cluster_id"] == cl]
        # Sort by membership probability (most "typical" first)
        sub = sub.sort_values("prob", ascending=False)
        sample = sub.head(N_SAMPLES_PER_CLUSTER)

        label = "NOISE" if cl == -1 else f"Cluster {cl}"
        print(f"\n{label}  (size={len(sub)})")
        for _, row in sample.iterrows():
            pid = row["page_id"]
            meta = id_to_meta.get(pid, {})
            title = meta.get("title", "")
            url = meta.get("url", "")
            extra = f"  | {title}" if title else ""
            extra += f"  {url}" if url else ""
            print(f"  id= {pid} prob={row['prob']:.2f}{extra}")


if __name__ == "__main__":
    main()