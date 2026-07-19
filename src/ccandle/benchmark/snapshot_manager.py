# Resolving snapshot references, and knowing what snapshots exist at all.
#
# find_available_snapshots() is the "what do I have" half — a pure
# ARTIFACT_DIR scan, no side effects, safe to call just to render a list.
# resolve_snapshot_reference() is the "make this into a working snapshot"
# half — may trigger dehydrate/rehydrate as a side effect. Kept in one
# module because both are just different views over the same naming
# convention (snapshot_naming.py), but callers should treat them as
# distinct: one is safe to call speculatively, the other isn't.

from datetime import date
from pathlib import Path

from ccandle.benchmark.snapshot_dehydrator import copy_and_dehydrate_snapshot
from ccandle.benchmark.snapshot_rehydrator import rehydrate_snapshot
from ccandle.benchmark.snapshot_namer import (
    infer_snapshot_date,
    canonical_path_for_date,
    parse_canonical_name,
    parse_date_string,
    HYDRATED_SUFFIX,
    DEHYDRATED_SUFFIX,
)
from ccandle.config.config_db import ARTIFACT_DIR

# Scans ARTIFACT_DIR for files matching our naming convention and
# buckets them by stage: {'dehydrated': {date: path}, 'hydrated': {date: path}}.
# Anything else is omitted from results.
def find_available_snapshots() -> dict[str, dict[date, Path]]:
    dehydrated: dict[date, Path] = {}
    hydrated: dict[date, Path] = {}

    if ARTIFACT_DIR.exists():
        for path in ARTIFACT_DIR.iterdir():
            if not path.is_file():
                continue
            parsed = parse_canonical_name(path)
            if parsed is None:
                continue
            snapshot_date, stage = parsed
            (hydrated if stage == "hydrated" else dehydrated)[snapshot_date] = path

    return {"dehydrated": dehydrated, "hydrated": hydrated}

def _resolve_from_date(
    snapshot_date: date,
    auto_hydrate: bool,
    raw_source_path: Path | None = None,
    known_dehydrated: Path | None = None,
) -> Path:
    hydrated_path = canonical_path_for_date(snapshot_date, HYDRATED_SUFFIX)
    if hydrated_path.exists():
        return hydrated_path

    if not auto_hydrate:
        raise FileNotFoundError(
            f"No hydrated snapshot for {snapshot_date.isoformat()} "
            f"({hydrated_path.name}), and auto_hydrate is disabled."
        )

    dehydrated_path = known_dehydrated or canonical_path_for_date(snapshot_date, DEHYDRATED_SUFFIX)
    if not dehydrated_path.exists():
        if raw_source_path is None:
            raise FileNotFoundError(
                f"No snapshot found for {snapshot_date.isoformat()}, and no source "
                f"path was given to build one."
            )
        dehydrated_path = copy_and_dehydrate_snapshot(raw_source_path)

    return rehydrate_snapshot(dehydrated_path)


def resolve_snapshot_reference(snapshot_input, auto_hydrate: bool = True) -> Path:
    """
    Accepts:
      - a bare date ("2026_07_15" or "2026-07-15")
      - a full path or bare filename pointing at one of our own canonical
        snapshots (.dehydrated.db / .hydrated.db)
      - a full path or bare filename pointing at an arbitrary raw source db

    Always returns a path to a .hydrated.db file, or raises
    FileNotFoundError. Same-day snapshots are the same snapshot — any
    input that resolves to a given date always resolves to that date's
    single canonical file.
    """
    text = str(snapshot_input)

    date_only = parse_date_string(text)
    if date_only is not None:
        return _resolve_from_date(date_only, auto_hydrate)

    candidate = Path(text).expanduser()
    if not candidate.is_absolute() and not candidate.exists():
        # bare filename — try it relative to the artifacts dir
        maybe = ARTIFACT_DIR / candidate.name
        if maybe.exists():
            candidate = maybe

    candidate = candidate.resolve()
    if not candidate.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_input}")

    parsed = parse_canonical_name(candidate)
    if parsed is not None:
        snapshot_date, stage = parsed
        if stage == "hydrated":
            return candidate
        return _resolve_from_date(snapshot_date, auto_hydrate, known_dehydrated=candidate)

    # arbitrary raw source db — not one of ours, infer its date from its data
    snapshot_date = infer_snapshot_date(candidate)
    return _resolve_from_date(snapshot_date, auto_hydrate, raw_source_path=candidate)