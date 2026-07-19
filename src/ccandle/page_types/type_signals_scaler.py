"""
Per-field, fixed-weight scaling for type signal vectors.

Replaces:
    X_scaled = StandardScaler().fit_transform(X)

with:
    X_scaled = scale_signal_vectors(X, signal_keys)

Design:
  - Every scaling constant below (the P95 dict) is FIXED, derived once from
    a representative profiling run (see profile_signal_fields.py output).
    Regenerating vectors for new pages does NOT recompute these constants -
    new pages are scaled against the same fixed reference. A page far more
    extreme than anything in the original profile will simply produce a
    scaled value > 1.0 in that dimension; this is fine for HDBSCAN/clustering
    and does not need clipping.
  - log1p is applied first (for fields where LOG1P=True), then divide by the
    fixed p95-of-log1p value. This keeps 0 -> 0 always.
  - Fields with shape "binary" / "ratio_0_1" / "leave as-is" get divisor 1.0
    (no-op) - they're already on a comparable scale.
  - CONSTANT_FIELDS (zero variance in the profile) are zeroed out in the
    output - they carry no information but are kept as columns so vector
    dimensionality / indexing doesn't change. If you'd rather physically drop
    them and shrink the vector to 57 dims, see DROP_CONSTANT_FIELDS below.

To recalibrate later (e.g. next year, per your note about deriving keyword
signals algorithmically): re-run profile_signal_fields.py on a fresh
representative sample, regenerate the P95_AFTER_LOG dict below from its
output, and nothing else needs to change.
"""
import numpy as np
from ccandle.page_types.type_signals_defs import SIGNAL_KEYS

# Fields with zero variance in the profiling run - carry no info.
CONSTANT_FIELDS = {'metric_flags', 'diagram_outside_tables'}

# Fields to log1p before dividing by their fixed divisor.
# = all "heavy_tail" + "mostly_zero" fields, plus b_release/b_performance/
# b_anti_release/b_anti_performance (recategorized as counts, see discussion).
LOG1P_FIELDS = {
    'word_count', 'image_count', 'image_density', 'task_count', 'mentions_count', 'mention_density',
    'diagram_count', 'bullet_count', 'header_count', 'digit_to_letter_ratio',

    'para_count', 'para_longest', 'para_share_long', 'para_average', 'para_lead_words',
    'para_lead_links',

    'link_count', 'link_git_count', 'link_jira_count', 'link_density', 'child_count',

    'table_count', 'minutes_in_tables', 'word_count_outside_tables', 'img_outside_tables',
    'sig_table_long_cell',

    'macro_toc', 'macro_struct_total', 'macro_panels', 'macro_expandables', 'macro_excerpts',

    't_month', 't_meeting_minutes', 't_workshop_minutes', 't_release', 't_performance',
    't_anti_landing', 't_anti_intro', 'h_solution',
    'b_meeting_minutes', 'b_workshop', 'b_bug',
    'b_release', 'b_performance', 'b_anti_release', 'b_anti_performance',
}

# Fixed divisors, in RAW units (i.e. p95 of the RAW field value, NOT of
# log1p(value)). The scaling function applies log1p to both the value and
# this divisor at scale-time, so you only need to maintain one number per
# field, taken directly from profile_signal_fields.py's p95 column.
#
# For fields not in LOG1P_FIELDS and not binary/ratio_0_1 (i.e. "leave as-is"
# small_int fields), the divisor is also taken from p95, applied directly
# (no log) - this just normalizes their scale toward ~1.0 without distorting
# their near-linear low-integer range.
#
# Binary / ratio_0_1 fields: divisor = 1.0 (no-op, already comparable scale).
# Constant fields: divisor irrelevant, value is zeroed regardless.
P95_RAW = {
    't_month': 0.0,
    't_g_meeting_minutes': 1.0,           # binary, no-op
    't_meeting_minutes': 1.0,
    't_g_workshop_minutes': 1.0,          # binary, no-op
    't_workshop_minutes': 1.0,
    't_release': 0.0,
    't_performance': 1.0,
    't_anti_landing': 1.0,
    't_intro': 1.0,                       # binary, no-op
    't_anti_intro': 1.0,
    't_solution': 1.0,                    # binary, no-op
    'h_solution': 2.0,
    'b_meeting_minutes': 1.0,
    'b_workshop': 0.0,
    'b_g_release': 1.0,                   # binary, no-op
    'b_release': 8.0,
    'b_anti_release': 3.0,
    'b_performance': 5.0,
    'b_anti_performance': 3.0,
    'b_bug': 1.0,
    'date': 1.0,                          # binary, no-op
    'date_bad': 1.0,                      # binary, no-op
    'date_reverse': 1.0,                  # binary, no-op
    'metric_flags': 0.0,                  # constant, zeroed
    'word_count': 1730.5,
    'image_count': 6.0,
    'link_count': 31.0,
    'link_git_count': 1.0,
    'link_jira_count': 4.0,
    'image_density': 2.029,
    'link_density': 9.276,
    'task_count': 4.0,
    'mentions_count': 14.0,
    'mention_density': 5.193,
    'diagram_count': 1.0,
    'bullet_count': 15.0,
    'header_count': 11.0,
    'digit_to_letter_ratio': 560.458,
    'para_count': 26.0,
    'para_longest': 190.0,
    'para_share_long': 0.222,
    'para_share_short': 1.0,               # ratio_0_1, no-op
    'para_average': 64.138,
    'para_lead_good': 1.0,                 # binary, no-op
    'para_lead_words': 75.0,
    'para_lead_links': 4.0,
    'child_count': 2.0,
    'table_count': 0.0,
    'minutes_in_tables': 1.0,
    'word_count_outside_tables': 1059.5,
    'diagram_outside_tables': 0.0,        # constant, zeroed
    'img_outside_tables': 5.0,
    'sig_table_has_cells': 1.0,           # binary, no-op
    'sig_cell_share_low_words': 1.0,      # ratio_0_1, no-op
    'sig_cell_share_empty': 1.0,          # ratio_0_1, no-op
    'sig_table_long_cell': 1.0,
    'sig_cell_many': 1.0,                 # binary, no-op

    'code_blocks': 4.0,
    'code_blocks_lines': 71.0,

    'lexic_jargon_share': 1.0,
    'lexic_rare_words_share': 1.0,
    'lexic_topical_focus': 1.0,
    'macro_toc': 1.0,
    'macro_jira_query': 1.0,              # binary, no-op
    'macro_struct_total': 1.0,
    'macro_panels': 0.0,
    'macro_expandables': 0.0,
    'macro_excerpts': 0.0,
    'macro_decisions': 1.0,               # binary, no-op
    'macro_children': 1.0,                # binary, no-op
}

# A few fields have p95 == 0 despite being non-constant (e.g. t_month,
# t_release, b_workshop, table_count, macro_panels, macro_expandables,
# macro_excerpts: zero_share is high enough that the 95th percentile itself
# is 0, even though max > 0). For these, fall back to their MAX as the
# divisor instead of p95, so nonzero values don't get divided by zero /
# blown up to huge scaled values. Listed here with their max from the
# profile.
FALLBACK_MAX_FOR_ZERO_P95 = {
    't_month': 2.0,
    't_release': 2.0,
    'b_workshop': 5.0,
    'table_count': 81.0,
    'macro_panels': 22.0,
    'macro_expandables': 192.0,
    'macro_excerpts': 4.0,
}


def _build_divisors():
    """Resolve final per-field divisors, applying log1p where needed and
    the zero-p95 fallback."""
    divisors = {}
    for key in SIGNAL_KEYS:
        if key in CONSTANT_FIELDS:
            divisors[key] = 1.0  # unused, value will be zeroed
            continue

        raw_divisor = P95_RAW[key]
        if raw_divisor == 0.0 and key in FALLBACK_MAX_FOR_ZERO_P95:
            raw_divisor = FALLBACK_MAX_FOR_ZERO_P95[key]

        if raw_divisor == 0.0:
            # shouldn't happen given the table above, but guard anyway
            raw_divisor = 1.0

        if key in LOG1P_FIELDS:
            divisors[key] = np.log1p(raw_divisor)
        else:
            divisors[key] = raw_divisor

    return divisors


_DIVISORS = _build_divisors()


def scale_signal_vectors(X, signal_keys=SIGNAL_KEYS):
    """
    Apply fixed, per-field scaling to a raw signal matrix X (n_pages x n_signals).

    - log1p applied to LOG1P_FIELDS (preserves 0 -> 0)
    - divide each column by its fixed divisor (from _DIVISORS)
    - CONSTANT_FIELDS are zeroed (or dropped, if DROP_CONSTANT_FIELDS=True)

    Returns X_scaled, same shape as X unless DROP_CONSTANT_FIELDS is True,
    in which case constant columns are removed (n_signals -> n_signals - len(CONSTANT_FIELDS)).
    """
    X = np.asarray(X, dtype=float)
    assert X.shape[1] == len(signal_keys), (
        f"X has {X.shape[1]} columns but signal_keys has {len(signal_keys)} entries"
    )

    X_scaled = np.zeros_like(X)

    for j, key in enumerate(signal_keys):
        col = X[:, j]

        if key in CONSTANT_FIELDS:
            X_scaled[:, j] = 0.0
            continue

        if key in LOG1P_FIELDS:
            col = np.log1p(np.clip(col, a_min=0, a_max=None))

        X_scaled[:, j] = col / _DIVISORS[key]

    return X_scaled


def scaled_signal_keys(signal_keys=SIGNAL_KEYS):
    return list(signal_keys)