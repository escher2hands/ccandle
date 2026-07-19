# Entry point for `ccandle benchmark SNAPSHOT_PATH_OR_NAME`.
#
# resolve_snapshot_reference accepts a full path, a bare filename, or a
# bare date, and always returns a path to a .hydrated.db file (building
# it via dehydrate + rehydrate if needed and auto_hydrate is allowed).
# compare_snapshots then pulls a same-shape overview of that snapshot and
# of the currently active db, matches spaces by space_id, and prints the
# delta for anything that matches.

from ccandle.analysis.space_overview import present_all_space_overviews
from ccandle.benchmark.snapshot_manager import resolve_snapshot_reference
from ccandle.config.config_db import PATH_DB
from ccandle.presentation.theme import *

NUMERIC_DELTA_SECTIONS = ("stats", "page_types")

# Metrics are derived purely from what the pipeline can pull out of the
# Confluence source of truth, so a metric present in one overview is
# guaranteed to be present in the other post-rehydration. Anything under
# this threshold is treated as "no real change" rather than float noise.
EQUALITY_THRESHOLD = 0.01
UNCHANGED_SENTINEL = "--"

def _index_by_space_id(spaces: list[dict]) -> dict:
    return {space["space_id"]: space for space in spaces}

# Per-key delta (new - old) for a flat numeric dict (stats or
# page_types).
def _delta_section(old_section: dict, new_section: dict) -> dict:
    if old_section.keys() != new_section.keys():
        raise ValueError(
            "Metric keys differ between snapshot and current db — this "
            "shouldn't happen post-rehydration.\n"
            f"  only in snapshot: {sorted(old_section.keys() - new_section.keys())}\n"
            f"  only in current:  {sorted(new_section.keys() - old_section.keys())}"
        )

    delta = {}
    for key in sorted(old_section):
        if old_section[key] is None:
            continue
        change = new_section[key] - old_section[key]
        delta[key] = change
    return delta


def _diff_space(old_space: dict, new_space: dict) -> dict:
    result = {
        "space_id": new_space["space_id"],
        "space_alias": new_space["space_alias"],
    }
    for section in NUMERIC_DELTA_SECTIONS:
        result[section] = _delta_section(old_space[section], new_space[section])
    return result


def compare_overviews(old_spaces: list[dict], new_spaces: list[dict]) -> dict:
    old_by_id = _index_by_space_id(old_spaces)
    new_by_id = _index_by_space_id(new_spaces)

    matched_ids = sorted(set(old_by_id) & set(new_by_id))
    only_old_ids = sorted(set(old_by_id) - set(new_by_id))
    only_new_ids = sorted(set(new_by_id) - set(old_by_id))
    return {
        "matched": [_diff_space(old_by_id[sid], new_by_id[sid]) for sid in matched_ids],
        "only_in_snapshot": [old_by_id[sid] for sid in only_old_ids],
        "only_in_current": [new_by_id[sid] for sid in only_new_ids],
    }


def compare_snapshots(snapshot_input: str, json_format=False, quiet=False):
    auto_hydrate = True
    try:
        hydrated_path = resolve_snapshot_reference(snapshot_input, auto_hydrate=auto_hydrate)
    except FileNotFoundError as e:
        print(
            f"{RED}" + "-" * WIDTH_NICE +
            f"\n{e}{RESET}\n"
        )
        return 1

    narrate = not (quiet or json_format)
    if narrate:
        print("\nComparing snapshot against current active db...\n")

    old_spaces = present_all_space_overviews(json_format=True, path_to_db=hydrated_path)
    new_spaces = present_all_space_overviews(json_format=True, path_to_db=PATH_DB)

    comparison = compare_overviews(old_spaces, new_spaces)

    return comparison
