# To quickly and easily compare the state and progress of our Confluence
# spaces across time, we can store snapshots in SharePoint (or anywhere
# convenient) and then compare them apples-to-apples against the current
# state of our spaces.
#
# Stage 1 (this file): copy an old snapshot into an isolated sqlite file,
# stripping every derived field, so it can later be 're-hydrated' with
# whatever the *current* processor produces. This intentionally does NOT
# touch rehydration/comparison — that's a separate stage built on top of
# the file this returns.

import sqlite3
from pathlib import Path
import hashlib

from ccandle.config.config_db import TABLE_PAGES, ARTIFACT_DIR

# --------------------------------------------------------------------------
# Single source of truth for field names + types. BASE_FIELDS is everything
# every snapshot has regardless of processor version. DERIVED_FIELDS is
# everything the *current* processor computes on top of that. Keeping them
# as one list of (name, type) tuples means the DDL and the column list used
# in INSERT/SELECT can never drift out of sync with each other — which is
# what actually broke the original version (schema-with-types was being
# used where a bare column list was needed).
# --------------------------------------------------------------------------

BASE_FIELDS: tuple[tuple[str, str], ...] = (
    ("id", "TEXT PRIMARY KEY"),

    ("title", "TEXT"),
    ("version", "INTEGER"),
    ("last_modified", "TEXT"),
    ("space_id", "TEXT"),
    ("html", "TEXT"),
    ("tiny_link", "TEXT"),
    ("retrieved_at", "TEXT"),

    ("child_list", "TEXT"),     # unfortunately, this is part of a processing step...but not really derived either.
)

# Not used by this stage yet — kept here only so the eventual rehydrate
# step has a single place to pull the derived schema from. Do not build
# a table with these columns during dehydration; that locks stage 2's
# schema into stage 1's code.
DERIVED_FIELDS: tuple[tuple[str, str], ...] = (
    ("plain_text", "TEXT"),
    ("lead_para", "TEXT"),
    ("eval_smell", "REAL"),
    ("eval_summary", "TEXT"),
    ("word_count", "INTEGER"),
    ("link_count", "INTEGER"),
    ("image_count", "INTEGER"),
    ("has_link_tree", "BOOLEAN"),
    ("eval_notes", "TEXT"),

    ("page_type", "TEXT"),
    ("mm_smell", "INTEGER"),
    ("rn_smell", "INTEGER"),
    ("pt_smell", "INTEGER"),
    ("ws_smell", "INTEGER"),
    ("sd_smell", "INTEGER"),
    ("ci_smell", "INTEGER"),
    ("lp_smell", "INTEGER"),

    ("links_list", "TEXT"),
    ("duplicate_list", "TEXT"),
    ("excerpts", "TEXT"),
)

BASE_COLUMNS: tuple[str, ...] = tuple(name for name, _ in BASE_FIELDS)
COMPARE_COLUMNS: tuple[str, ...] = BASE_COLUMNS + tuple(name for name, _ in DERIVED_FIELDS)


def _ddl(fields: tuple[tuple[str, str], ...]) -> str:
    return ",\n    ".join(f"{name} {sqltype}" for name, sqltype in fields)

def _col_list(columns: tuple[str, ...]) -> str:
    return ", ".join(columns)


DEHYDRATED_SNAP_DDL = _ddl(BASE_FIELDS)
COMPARE_SNAP_DDL = _ddl(BASE_FIELDS + DERIVED_FIELDS)  # for stage 2, not used here


# expects an OPEN DB CONNECTION. This won't open or close the connection.
def create_dehydrated_table(db_conn: sqlite3.Connection) -> None:
    cur = db_conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_PAGES} ({DEHYDRATED_SNAP_DDL})")
    db_conn.commit()


def _dehydrated_path_from_snapshot(snapshot_path: Path) -> Path:
    h = hashlib.md5(str(snapshot_path.resolve()).encode()).hexdigest()[:8]
    return ARTIFACT_DIR / f"{snapshot_path.stem}_{h}.dehydrated.db"

def _copy_snapshot(cur: sqlite3.Cursor) -> int:
    """
    Copy base fields from the attached source db into the dehydrated
    table, keeping only pages with non-empty HTML.
    """
    columns = _col_list(BASE_COLUMNS)
    insert_sql = f"""
        INSERT INTO {TABLE_PAGES} ({columns})
        SELECT {columns}
        FROM src.{TABLE_PAGES}
        WHERE html IS NOT NULL AND TRIM(html) != ''
    """
    print(f"Copying src.{TABLE_PAGES} -> {TABLE_PAGES} (dehydrated schema).")
    cur.execute(insert_sql)
    return cur.rowcount


def copy_and_dehydrate_snapshot(snapshot_input, source_html_column: str = "html_body") -> Path:
    """
    Copy an old (single-table) Confluence snapshot into a fresh sqlite
    file containing only the base fields any processor version can
    produce. This is the artifact a later rehydrate step reads from.
    """
    snapshot_path = Path(snapshot_input).expanduser().resolve()
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    dehydrated_path = _dehydrated_path_from_snapshot(snapshot_path)
    if dehydrated_path.exists():
        dehydrated_path.unlink()

    conn = sqlite3.connect(dehydrated_path)
    try:
        cur = conn.cursor()
        # Single-writer, build-once file: WAL buys nothing here and just
        # leaves -wal/-shm siblings next to the artifact. Plain + fast.
        cur.executescript("""
            PRAGMA synchronous = OFF;
            PRAGMA temp_store = MEMORY;
        """)

        cur.execute("ATTACH DATABASE ? AS src", (str(snapshot_path),))
        try:
            tables = {row[0] for row in cur.execute(
                "SELECT name FROM src.sqlite_master WHERE type='table'"
            )}
            if TABLE_PAGES not in tables:
                raise ValueError(
                    f"{snapshot_path} has no '{TABLE_PAGES}' table "
                    f"(found: {sorted(tables)})"
                )

            create_dehydrated_table(conn)
            copied = _copy_snapshot(cur)
            conn.commit()
        finally:
            cur.execute("DETACH DATABASE src")
    finally:
        conn.close()

    print(f"Copied {copied} page(s) -> {dehydrated_path}")
    return dehydrated_path