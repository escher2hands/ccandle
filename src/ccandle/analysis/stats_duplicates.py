"""
Duplicate-candidate generation via type-signal nearest-neighbor search.
We are not looking for "similar" pages here -- duplicates differ by at most 
a handful of words (a date swap, a line break, a panel
that's present on one copy and absent on the other). Because the type-signal
vector already encodes word count, paragraph count, link count, table count,
and a few dozen other structural counts, a true duplicate pair's vectors are
expected to be near-identical -- often exactly identical -- in that space.

So instead of partitioning the corpus into clusters (which risks splitting a
close pair across an arbitrary boundary -- the bucket-cutoff problem), we
directly search for pairs of pages within a tight Euclidean radius of each
other. Every pair is evaluated on its own distance, so there's no
cutoff/boundary case to worry about: a true near-duplicate pair can't be
"split" by where some unrelated cluster boundary happens to fall.

Output is a list of (page_id_a, page_id_b, distance) candidate PAIRS, not
clusters. These are the exact pairs worth running through the (expensive)
Jaccard shingle comparison -- there's no need to compare every page within a
loose group against every other page in that group, the way the old
cluster-then-pairwise approach did.
"""

from collections import namedtuple
from sklearn.neighbors import NearestNeighbors
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.page_types.type_signals_defs import THRESH_PAGE_EMPTY
from ccandle.page_types.decompose_page_into_type_signals import load_type_signal_vectors
import sqlite3, json
from tqdm import tqdm

from ccandle.presentation.theme import DIM, RESET

# Set this higher for more fuzzy matching, lower if you need more exactness.
# Remember, this is the first pass on type signals. A second pass will make
# actual jaccard based matching
T_SIGNALS_THRESHOLD = 0.7

# Tried euclidean and manhattan, and found euclidean is just fine.
# Not much of a difference. So euclidean is fine.
DEFAULT_METRIC = "euclidean"

# Jaccard similarity floor for the second pass, and the shingle window size
# (consecutive words per shingle). Both apply only to the candidate pairs
# the type-signal pass already narrowed things down to.
JACCARD_SIMILARITY_THRESHOLD = 0.84
SHINGLE_SIZE = 5

CandidatePair = namedtuple("CandidatePair", ["page_id_a", "page_id_b", "distance"])
JaccardDuplicate = namedtuple(
    "JaccardDuplicate",
    ["page_id_a", "page_id_b", "jaccard_similarity", "signal_distance"],
)

def scan_for_duplicates_in_corpus(fuzziness=1.0, path_to_db=PATH_DB):
    pre_filter_sensitivity = 0.7 / fuzziness
    duplicate_threshold = 0.85 / fuzziness
    pairs = find_duplicate_pages(epsilon=pre_filter_sensitivity, jaccard_threshold=duplicate_threshold, path_to_db=path_to_db)
    groups = group_jaccard_duplicates(pairs)
    mapping = build_duplicate_mapping(groups)
    if fuzziness == 1.0:            # only store duplicate mapping when fuzziness is a stable score.
        _store_duplicate_lists(mapping, path_to_db)
    return duplicate_mapping_to_groups(mapping)

# Full pipeline, start to finish: type-signal nearest-neighbor candidate
# generation, then Jaccard shingle comparison restricted to those
# candidates. Two SQL queries total for the whole run -- one for vectors,
# one for metadata -- regardless of corpus size, since metadata is loaded
# once here and shared across both stages.
def find_duplicate_pages(epsilon=T_SIGNALS_THRESHOLD, metric=DEFAULT_METRIC,
                         jaccard_threshold=JACCARD_SIMILARITY_THRESHOLD,
                         k_shingle=SHINGLE_SIZE, *, path_to_db):
    ids, X, meta = _load_filtered_vectors(path_to_db)
    candidate_pairs = _find_candidate_pairs(ids, X, epsilon, metric)
    print(f"{DIM}Completed pre-filtering to find similar pages. \n"
          f"We'll compare these to find near-exact duplicates.{RESET}")
    blob = find_jaccard_duplicates(candidate_pairs, meta, jaccard_threshold, k_shingle)
    return blob


# Bulk-load word_count and plain_text for every page in a single query.
# Mirrors load_type_signal_vectors's own unfiltered load -- no per-id
# filtering here, so there's no risk of hitting SQLite's bound-parameter
# limit on a 10K-row IN(...) clause. Replaces what used to be one
# get_field_in_pages call per page, per field.
def _load_page_meta(path_to_db):
    with sqlite3.connect(path_to_db) as conn:
        rows = conn.execute(
            f"SELECT id, word_count, plain_text FROM {TABLE_PAGES}"
        ).fetchall()
    return {pid: (word_count, plain_text) for pid, word_count, plain_text in rows}

# Drop pages below the minimum word count, using already-loaded metadata
# instead of a query per page.
def _filter_non_empty_pages(pids, meta):
    kept = []
    for pid in pids:
        entry = meta.get(pid)
        if not entry:
            continue
        word_count, _ = entry
        if word_count and word_count >= THRESH_PAGE_EMPTY:
            kept.append(pid)
    return kept

# Loads vectors + bulk metadata (2 queries total) and filters down to the
# non-empty page set. Shared by find_duplicate_candidate_pairs (standalone
# tuning use) and find_duplicate_pages (full pipeline) so metadata never
# gets loaded more than once per run.
def _load_filtered_vectors(path_to_db):
    ids, X = load_type_signal_vectors(path_to_db=path_to_db)
    if not ids:
        return [], X, {}

    meta = _load_page_meta(path_to_db)
    keep_set = set(_filter_non_empty_pages(ids, meta))
    keep_idx = [i for i, pid in enumerate(ids) if pid in keep_set]
    if len(keep_idx) < 2:
        return [], X, meta

    ids = [ids[i] for i in keep_idx]
    X = X[keep_idx]
    return ids, X, meta


# Pure radius-neighbor search over an already-loaded (ids, X) pair.
def _find_candidate_pairs(ids, X, epsilon, metric=DEFAULT_METRIC):
    n = len(ids)
    if n < 2:
        return []

    nn = NearestNeighbors(radius=epsilon, algorithm="auto", metric=metric)
    nn.fit(X)
    distances, neighbor_idxs = nn.radius_neighbors(X)

    pairs = {}
    for i, (dists, neighbors) in enumerate(zip(distances, neighbor_idxs)):
        for dist, j in zip(dists, neighbors):
            if j <= i:
                continue  # skip self-match, and the reverse of a pair we already saw
            key = (ids[i], ids[j]) if ids[i] < ids[j] else (ids[j], ids[i])
            if key not in pairs or dist < pairs[key]:
                pairs[key] = float(dist)

    return sorted(
        (CandidatePair(a, b, d) for (a, b), d in pairs.items()),
        key=lambda p: p.distance,
    )

# Lowercase, strip, collapse whitespace. Deliberately conservative beyond
# that -- doesn't strip punctuation or the [[Heading: ...]] / [[link to: ...]]
# structural markup, since those are meaningful, consistently-applied tokens
# that should shingle the same way across truly-duplicate pages.
def _normalize_text(text):
    return " ".join(text.lower().split())


# k-word shingles: overlapping windows of k consecutive words.
def _make_shingles(text, k):
    words = text.split()
    if len(words) < k:
        return {tuple(words)} if words else set()
    return {tuple(words[i: i + k]) for i in range(len(words) - k + 1)}


# Our proper page comparison engine, using shingles
def _jaccard_similarity(set_a, set_b):
    if not set_a and not set_b:
        return 1.0
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union else 0.0

# Run Jaccard shingle comparison on the specific candidate pairs produced
# by find_duplicate_candidate_pairs -- not on clusters. The nearest-neighbor
# pass already tells us exactly which pairs are worth comparing, so there's
# no all-against-all combinations() over a group like the old clusters-based
# version did.
#
# `meta` is the same {page_id: (word_count, plain_text)} dict produced by
# _load_page_meta -- pass it through so this step needs zero additional
# queries.
#
# Shingles are computed once per page (not once per pair), since a page can
# appear in multiple candidate pairs and shingling is the expensive part.
#
# Returns: list of JaccardDuplicate(page_id_a, page_id_b, jaccard_similarity,
# signal_distance), sorted by descending similarity. signal_distance is
# carried through from the candidate pair for later threshold tuning.
def find_jaccard_duplicates(candidate_pairs, meta, threshold=JACCARD_SIMILARITY_THRESHOLD,
                            k_shingle=SHINGLE_SIZE):
    if not candidate_pairs:
        return []

    page_ids = {pid for pair in candidate_pairs for pid in (pair.page_id_a, pair.page_id_b)}

    shingles_by_id = {}
    for pid in tqdm(page_ids, desc="Shingling pages"):
        entry = meta.get(pid)
        if entry and entry[1]:
            shingles_by_id[pid] = _make_shingles(_normalize_text(entry[1]), k=k_shingle)

    results = []
    for pair in tqdm(candidate_pairs, desc="Comparing pairs"):
        a, b = pair.page_id_a, pair.page_id_b
        if a not in shingles_by_id or b not in shingles_by_id:
            continue
        sim = _jaccard_similarity(shingles_by_id[a], shingles_by_id[b])
        if sim >= threshold:
            results.append(JaccardDuplicate(a, b, sim, pair.distance))

    return sorted(results, key=lambda r: r.jaccard_similarity, reverse=True)

def group_jaccard_duplicates(jaccard_duplicates):
    uf = UnionFind()
    for dup in jaccard_duplicates:
        uf.union(dup.page_id_a, dup.page_id_b)

    groups = {}
    for dup in jaccard_duplicates:
        for pid in (dup.page_id_a, dup.page_id_b):
            root = uf.find(pid)
            groups.setdefault(root, set()).add(pid)

    return [
        sorted(group, key=lambda x: int(x))
        for group in groups.values()
        if len(group) > 1
    ]

# Serialize at build time so stored values are independent strings,
# not aliased references to the same live list.
def build_duplicate_mapping(groups):
    return {
        pid: json.dumps(group)
        for group in groups
        for pid in group
    }
def duplicate_mapping_to_groups(duplicate_mapping):
    return [
        json.loads(dup_json)
        for dup_json in set(duplicate_mapping.values())
    ]

class UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, x):
        if x not in self.parent:
            self.parent[x] = x
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, x, y):
        px, py = self.find(x), self.find(y)
        if px != py:
            self.parent[py] = px

# mapping: dict {page_id: [pid1, pid2, ...]}
def _store_duplicate_lists(mapping, path_to_db):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        # clear the old ones, so that we have a cleanly built list with no stales
        query = f"UPDATE {TABLE_PAGES} SET duplicate_list = NULL"
        cur.execute(query)

        rows = [
            (dup_list, pid)
            for pid, dup_list in mapping.items()
        ]
        query = f"""UPDATE {TABLE_PAGES} SET duplicate_list = ? WHERE id = ?"""
        cur.executemany(query, rows)


def fetch_unique_duplicate_groups(space_id=None, path_to_db=PATH_DB):
    with sqlite3.connect(path_to_db) as conn:
        space_filter = f"space_id = {space_id}" if space_id else "1=1"
        query = f"""SELECT duplicate_list FROM {TABLE_PAGES} WHERE duplicate_list IS NOT NULL AND {space_filter}"""
        cur = conn.cursor()
        cur.execute(query)
        rows = cur.fetchall()

    seen = set()
    unique_groups = []

    for (dup_json,) in rows:
        group = tuple(json.loads(dup_json))  # already sorted
        if group not in seen:
            seen.add(group)
            unique_groups.append(list(group))

    return unique_groups
