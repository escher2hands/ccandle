from ccandle.db.db_query_utils import query_db_results
from collections import Counter
import json

def get_all_labels_in_pages(space_id=None):
    counter = Counter()
    if space_id:
        space_filter = f"space_id = ?"
        params = (space_id,)
    else:
        space_filter = "1=1"
        params = None
    from_pages = query_db_results(select_query='labels', where_clause=space_filter, params=params)
    for (labels_json,) in from_pages:
        counter.update(json.loads(labels_json)) if labels_json else 0

    results = [
        {"label": label, "page_count": count}
        for label, count in counter.most_common()
    ]
    return results

# cluster labels such that every pair must be above min_similarity
def gather_likely_redundant_labels(labels_with_counts: list[dict], fuzziness: float = 1.0, linkage_method="complete") -> list[list[dict]]:
    import numpy as np
    from scipy.cluster.hierarchy import linkage, fcluster
    from scipy.spatial.distance import squareform
    from collections import defaultdict
    from rapidfuzz import fuzz, process

    MIN_SIMILARITY = 80
    labels = [item["label"] for item in labels_with_counts]
    n = len(labels)
    if n < 2:
        return []

    sim = process.cdist(labels, labels, scorer=fuzz.WRatio).astype(float)
    np.fill_diagonal(sim, 100.0)

    dist = 100.0 - sim
    np.fill_diagonal(dist, 0.0)
    dist = (dist + dist.T) / 2  # guard against float asymmetry

    condensed = squareform(dist, checks=False)
    Z = linkage(condensed, method=linkage_method)

    max_distance = (100 - MIN_SIMILARITY) * fuzziness
    cluster_ids = fcluster(Z, t=max_distance, criterion="distance")

    groups = defaultdict(list)
    for idx, cid in enumerate(cluster_ids):
        groups[cid].append(labels_with_counts[idx])

    clusters = [
        sorted(g, key=lambda x: x["page_count"], reverse=True)
        for g in groups.values()
        if len(g) > 1
    ]
    clusters.sort(key=lambda c: sum(item["page_count"] for item in c), reverse=True)
    return clusters
