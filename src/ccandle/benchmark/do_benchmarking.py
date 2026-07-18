# Entry point for `ccandle benchmark SNAPSHOT_PATH_OR_NAME`.
#
# Loads (or reuses) a normalized snapshot, pulls a same-shape overview of
# both the snapshot and the currently active db, matches spaces by
# space_id, and prints the delta for anything that matches. Anything that
# doesn't match (space added/removed since the snapshot was taken) gets
# printed raw instead of diffed against nothing.

import json
from pathlib import Path

from ccandle.benchmark.snapshot_dehydrator import copy_and_dehydrate_snapshot, _dehydrated_path_from_snapshot
from ccandle.benchmark.snapshot_rehydrator import rehydrate_snapshot, _normalized_path_from_dehydrated
from ccandle.config.config_db import PATH_DB
from ccandle.analysis.space_overview import present_all_space_overviews
from ccandle.presentation.theme import *

NUMERIC_DELTA_SECTIONS = ("stats", "page_types")

# Metrics are derived purely from what the pipeline can pull out of the
# Confluence source of truth, so a metric present in one overview is
# guaranteed to be present in the other post-rehydration. Anything under
# this threshold is treated as "no real change" rather than float noise.
DEFAULT_EQUALITY_THRESHOLD = 0.01
UNCHANGED_SENTINEL = "--"


def resolve_snapshot_reference(snapshot_input: str) -> Path:
    # TODO: look up snapshot_input in the snapshot registry once it exists.
    return Path(snapshot_input).expanduser().resolve()


def _expected_normalized_path(snapshot_path: Path) -> Path:
    """Pure path computation, mirroring the naming both stages already
    use, without doing any of the actual dehydrate/rehydrate work. Lets
    us check for a cache hit before paying for either step — the old
    version's "reuse if it exists" shortcut, restored here since
    copy_and_dehydrate_snapshot unconditionally recreates its output."""
    return _normalized_path_from_dehydrated(_dehydrated_path_from_snapshot(snapshot_path))


def _load_or_reuse_normalized(snapshot_path: Path, quiet: bool = False) -> Path:
    normalized_path = _expected_normalized_path(snapshot_path)
    if normalized_path.exists():
        if not quiet:
            print("Found a 'hydrated' version of your snapshot! We'll use it for this benchmark.")
        return normalized_path

    if not quiet:
        print("Loading your snapshot...")
    dehydrated_path = copy_and_dehydrate_snapshot(snapshot_path)

    if not quiet:
        print("Reprocessing with current algorithms...")
    return rehydrate_snapshot(dehydrated_path)


def _index_by_space_id(spaces: list[dict]) -> dict:
    return {space["space_id"]: space for space in spaces}

# Per-key delta (new - old) for a flat numeric dict (stats or
# page_types).
def _delta_section(old_section: dict, new_section: dict, equality_threshold: float) -> dict:
    if old_section.keys() != new_section.keys():
        raise ValueError(
            "Metric keys differ between snapshot and current db — this "
            "shouldn't happen post-rehydration.\n"
            f"  only in snapshot: {sorted(old_section.keys() - new_section.keys())}\n"
            f"  only in current:  {sorted(new_section.keys() - old_section.keys())}"
        )

    delta = {}
    for key in sorted(old_section):
        change = new_section[key] - old_section[key]
        delta[key] = change if abs(change) >= equality_threshold else UNCHANGED_SENTINEL
    return delta


def _diff_space(old_space: dict, new_space: dict, equality_threshold: float) -> dict:
    result = {
        "space_id": new_space["space_id"],
        "space_alias": new_space["space_alias"],
    }
    for section in NUMERIC_DELTA_SECTIONS:
        result[section] = _delta_section(old_space[section], new_space[section], equality_threshold)
    return result


def compare_overviews(
    old_spaces: list[dict],
    new_spaces: list[dict],
    equality_threshold: float = DEFAULT_EQUALITY_THRESHOLD,
) -> dict:
    old_by_id = _index_by_space_id(old_spaces)
    new_by_id = _index_by_space_id(new_spaces)

    matched_ids = sorted(set(old_by_id) & set(new_by_id))
    only_old_ids = sorted(set(old_by_id) - set(new_by_id))
    only_new_ids = sorted(set(new_by_id) - set(old_by_id))

    return {
        "matched": [_diff_space(old_by_id[sid], new_by_id[sid], equality_threshold) for sid in matched_ids],
        "only_in_snapshot": [old_by_id[sid] for sid in only_old_ids],
        "only_in_current": [new_by_id[sid] for sid in only_new_ids],
    }


def _fmt_delta(value) -> str:
    if value == UNCHANGED_SENTINEL:
        return f"{DIM}{UNCHANGED_SENTINEL}{RESET}"
    if isinstance(value, float):
        value = round(value, 4)
    sign = "+" if value > 0 else ""
    text = f"{sign}{value}"
    return f"{RED}{text}{RESET}" if value < 0 else text


def _print_delta_report(comparison: dict) -> None:
    if not any(comparison.values()):
        print("No spaces found in either db.")
        return

    for space in comparison["matched"]:
        print(f"\n=== {space['space_alias']} ({space['space_id']}) ===")
        for section in NUMERIC_DELTA_SECTIONS:
            print(f"  {section}:")
            for key, value in space[section].items():
                print(f"    {key}: {_fmt_delta(value)}")

    if comparison["only_in_snapshot"]:
        print(f"\n{RED}Only in snapshot (missing from current db):{RESET}")
        for space in comparison["only_in_snapshot"]:
            print(json.dumps(space, indent=2))

    if comparison["only_in_current"]:
        print(f"\n{RED}Only in current db (not in snapshot):{RESET}")
        for space in comparison["only_in_current"]:
            print(json.dumps(space, indent=2))


def compare_snapshots(
    snapshot_input: str,
    json_format: bool = False,
    quiet: bool = False,
    equality_threshold: float = DEFAULT_EQUALITY_THRESHOLD,
) -> int:
    snapshot_path = resolve_snapshot_reference(snapshot_input)

    if not snapshot_path.exists():
        print(
            f"{RED}" + "-" * WIDTH_NICE +
            f"\nSnapshot not found: {snapshot_path}{RESET}"
            f"\n\n{RED}{DIM}Double check the path or name you gave for the "
            f"snapshot you'd like to compare.\n{RESET}"
        )
        return 1

    # json output should be pipe-clean; suppress progress narration for it
    narrate = not (quiet or json_format)

    normalized_path = _load_or_reuse_normalized(snapshot_path, quiet=not narrate)

    if narrate:
        print("\nComparing snapshot against current active db...\n")

    old_spaces = present_all_space_overviews(json_format=True, path_to_db=normalized_path)
    new_spaces = present_all_space_overviews(json_format=True, path_to_db=PATH_DB)

    comparison = compare_overviews(old_spaces, new_spaces, equality_threshold)

    if json_format:
        print(json.dumps(comparison, indent=2))
    else:
        _print_delta_report(comparison)

    return 0