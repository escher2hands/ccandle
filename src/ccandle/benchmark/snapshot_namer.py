# Shared naming convention for benchmark snapshot artifacts.
#
# We only ever create two kinds of file, always named the same way:
#   confluence_mirror_YYYY_MM_DD.dehydrated.db
#   confluence_mirror_YYYY_MM_DD.hydrated.db
#
# The date always comes from the data itself (MAX(retrieved_at) in
# TABLE_PAGES) — never from whatever the input file happened to be
# called. This is deliberate.
#
# Two snapshots retrieved on the same day intentionally collapse into
# one file — Confluence doesn't move fast enough for same-day
# granularity to matter for benchmarking.

import re
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path

from ccandle.config.config_db import TABLE_PAGES, ARTIFACT_DIR

SNAPSHOT_NAME_PREFIX = "confluence_mirror"
DEHYDRATED_SUFFIX = ".dehydrated.db"
HYDRATED_SUFFIX = ".hydrated.db"

_DATE_FORMAT = "%Y_%m_%d"
_NAME_RE = re.compile(
    rf"^{re.escape(SNAPSHOT_NAME_PREFIX)}_(\d{{4}}_\d{{2}}_\d{{2}})\.(dehydrated|hydrated)\.db$"
)

# we pull this from querying the latest 'retrieved_at' value in the db
def infer_snapshot_date(path_to_db: Path) -> date:
    conn = sqlite3.connect(path_to_db)
    try:
        row = conn.execute(f"SELECT MAX(retrieved_at) FROM {TABLE_PAGES}").fetchone()
    finally:
        conn.close()

    raw = row[0] if row else None
    if not raw:
        raise ValueError(f"No retrieved_at values found in {path_to_db} — can't infer a snapshot date.")

    return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()


def canonical_path_for_date(snapshot_date: date, suffix: str) -> Path:
    return ARTIFACT_DIR / f"{SNAPSHOT_NAME_PREFIX}_{snapshot_date.strftime(_DATE_FORMAT)}{suffix}"

# Returns (date, 'dehydrated' | 'hydrated') if path matches our
# naming convention, else None. Pure filename parsing.
def parse_canonical_name(path: Path) -> tuple[date, str] | None:
    match = _NAME_RE.match(path.name)
    if not match:
        return None
    date_str, stage = match.groups()
    return datetime.strptime(date_str, _DATE_FORMAT).date(), stage

# friendly string date parsing, so both '2026_07_15' and '2026-07-15'
# will succeed
def parse_date_string(text: str) -> date | None:
    for fmt in (_DATE_FORMAT, "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None

# A throwaway working path in ARTIFACT_DIR, used while building a
# snapshot before its real (date-derived) name is known.
def scratch_path(label: str, suffix: str) -> Path:
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    return ARTIFACT_DIR / f".tmp_{label}_{uuid.uuid4().hex[:8]}{suffix}"

# Infers scratch_path_to_db's date from its own data and renames it to
# our canonical name for that date, overwriting any existing snapshot
# for the same day (intentional — see module docstring). This is the
# *only* place a snapshot's final name gets decided.
def finalize_snapshot_name(scratch_path_to_db: Path, suffix: str) -> Path:
    snapshot_date = infer_snapshot_date(scratch_path_to_db)
    canonical_path = canonical_path_for_date(snapshot_date, suffix)

    if canonical_path.exists() and canonical_path != scratch_path_to_db:
        canonical_path.unlink()
    if scratch_path_to_db != canonical_path:
        scratch_path_to_db.rename(canonical_path)

    return canonical_path