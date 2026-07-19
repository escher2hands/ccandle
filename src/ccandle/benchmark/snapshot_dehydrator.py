# Stage 1: copy an old (single-table) Confluence snapshot into an
# isolated sqlite file, stripped down to only the "base" fields any
# processor version can produce. This is the artifact stage 2 (rehydrate)
# reads from. Output is always named per snapshot_naming's convention,
# derived from the data's own retrieved_at value — never from the input
# file's path.

import sqlite3
from pathlib import Path
from ccandle.db.table_utils import create_table
from ccandle.config.config_db import TABLE_PAGES, TABLE_VECTORS
from ccandle.benchmark.snapshot_namer import scratch_path, finalize_snapshot_name, DEHYDRATED_SUFFIX
from ccandle.pages.vectors.schema_table_vectors import SCHEMA_VECTORS

# --------------------------------------------------------------------------
# Single source of truth for field names + types. DEHYDRATED_SCHEMA is everything
# every snapshot has regardless of processor version. HYDRATED_SCHEMA is
# everything the *current* processor computes on top of that.
# --------------------------------------------------------------------------

DEHYDRATED_SCHEMA: tuple[tuple[str, str], ...] = (
    ("id", "TEXT PRIMARY KEY"),
    ("title", "TEXT"),
    ("version", "INTEGER"),
    ("last_modified", "TEXT"),
    ("space_id", "TEXT"),
    ("html", "TEXT"),
    ("tiny_link", "TEXT"),
    ("retrieved_at", "TEXT"),

    ("child_list", "TEXT"),
)

HYDRATED_SCHEMA: tuple[tuple[str, str], ...] = (
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
    ("child_list", "TEXT"),
    ("duplicate_list", "TEXT"),
    ("excerpts", "TEXT"),
)

BASE_COLUMNS: tuple[str, ...] = tuple(name for name, _ in DEHYDRATED_SCHEMA)
COMPARE_COLUMNS: tuple[str, ...] = BASE_COLUMNS + tuple(name for name, _ in HYDRATED_SCHEMA)


def _ddl(fields: tuple[tuple[str, str], ...]) -> str:
    return ",\n    ".join(f"{name} {sqltype}" for name, sqltype in fields)

def _col_list(columns: tuple[str, ...]) -> str:
    return ", ".join(columns)


DEHYDRATED_SNAP_DDL = _ddl(DEHYDRATED_SCHEMA)
COMPARE_SNAP_DDL = _ddl(DEHYDRATED_SCHEMA + HYDRATED_SCHEMA)  # used by the rehydrate stage


def create_dehydrated_table(db_conn: sqlite3.Connection) -> None:
    """Expects an OPEN DB CONNECTION; does not open or close it."""
    cur = db_conn.cursor()
    cur.execute(f"CREATE TABLE IF NOT EXISTS {TABLE_PAGES} ({DEHYDRATED_SNAP_DDL})")
    db_conn.commit()


# copy all rows over
def _copy_snapshot(cur: sqlite3.Cursor, source_html_column: str = "html_body") -> int:
    columns = _col_list(BASE_COLUMNS)
    insert_sql = f"""
        INSERT INTO {TABLE_PAGES} ({columns})
        SELECT {columns}
        FROM src.{TABLE_PAGES}
    """
    print(f"Copying src.{TABLE_PAGES} -> {TABLE_PAGES} (dehydrated schema).")
    cur.execute(insert_sql)
    return cur.rowcount


def copy_and_dehydrate_snapshot(snapshot_input, source_html_column: str = "html_body") -> Path:
    snapshot_path = Path(snapshot_input).expanduser().resolve()
    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    tmp_path = scratch_path("dehydrate", DEHYDRATED_SUFFIX)

    conn = sqlite3.connect(tmp_path)
    try:
        cur = conn.cursor()
        cur.executescript("PRAGMA synchronous = OFF; PRAGMA temp_store = MEMORY;")
        cur.execute("ATTACH DATABASE ? AS src", (str(snapshot_path),))
        try:
            tables = {row[0] for row in cur.execute(
                "SELECT name FROM src.sqlite_master WHERE type='table'"
            )}
            if TABLE_PAGES not in tables:
                raise ValueError(
                    f"{snapshot_path} has no '{TABLE_PAGES}' table (found: {sorted(tables)})"
                )

            create_dehydrated_table(conn)
            # create_table(TABLE_VECTORS, SCHEMA_VECTORS, path_to_db=tmp_path)
            copied = _copy_snapshot(cur, source_html_column=source_html_column)
            conn.commit()
        finally:
            cur.execute("DETACH DATABASE src")
    finally:
        conn.close()

    dehydrated_path = finalize_snapshot_name(tmp_path, DEHYDRATED_SUFFIX)
    print(f"Copied {copied} page(s) -> {dehydrated_path}")
    return dehydrated_path