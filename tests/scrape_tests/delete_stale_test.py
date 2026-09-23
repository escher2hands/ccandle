"""
Tests for delete_dead_db_pages (final step of sync_pages_from_cloud).

Unlike the earlier scrape steps, this function has no injectable
_store_x-style boundary -- it opens sqlite3.connect(PATH_DB) directly and
runs real DELETE statements. Mocking that away would mean not testing the
one thing this function actually does. So here we deviate from "mock the
DB" to "point PATH_DB at a real temporary SQLite file with the production
schema," and only mock the two genuine boundaries:
  - get_all_ids_in_pages(): the source of "what does local think it has"
  - render_table(): pure presentation, not this function's job to verify

We assert on real DB state after each call (what rows actually remain)
rather than on internal call arguments, since that's the actual contract
this function has to uphold: it deletes only, and exactly, the rows that
are locally tracked but absent from the cloud id list.

We do NOT assert on the exact wording of every print statement -- most of
them describe an outcome (nothing deleted / N pages deleted) that's
already verified directly against DB state, so re-asserting it via stdout
would just be checking the same thing twice, more fragile the second
time. The one exception is the ">50 and >10%" mass-deletion warning: since
printing IS the entire observable behavior of that branch (no DB or
other side effect differs), that one is worth checking via capsys -- and
even then, against the real HINT_MANY_FOR_DELETION constant imported from
the module, not a hand-typed copy of its text.
"""

import sqlite3
from types import SimpleNamespace

import pytest

from ccandle.sync.delete_dead_pages import (
    delete_dead_db_pages,
    TABLE_PAGES,
    HINT_MANY_FOR_DELETION,
)

MODULE = "ccandle.pages.delete_dead_pages"  # adjust to your actual module path


# ---------------------------------------------------------------------------
# Real, temporary SQLite DB with the production schema
# ---------------------------------------------------------------------------

@pytest.fixture
def local_pages_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_ccandle.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"""
            CREATE TABLE {TABLE_PAGES} (
                id TEXT PRIMARY KEY,
                version INTEGER,
                space_id TEXT,
                title TEXT,
                tiny_link TEXT,
                status TEXT,
                retrieved_at TEXT
            )
            """
        )

    monkeypatch.setattr(f"ccandle.sync.delete_dead_pages.PATH_DB", str(db_path))

    render_table_calls = []
    monkeypatch.setattr(
        f"ccandle.sync.delete_dead_pages.render_table",
        lambda dead_pages, columns: render_table_calls.append(dead_pages),
    )

    def seed(rows):
        """rows: list of dicts with at least 'id'; 'space_id'/'title' optional.
        Also wires up get_all_ids_in_pages() to report exactly these ids as
        the local universe, mirroring how in production that function and
        this table are always kept consistent (same underlying data)."""
        with sqlite3.connect(db_path) as conn:
            for r in rows:
                conn.execute(
                    f"INSERT INTO {TABLE_PAGES} (id, space_id, title) VALUES (?, ?, ?)",
                    (r["id"], r.get("space_id", "SPACE1"), r.get("title", f"Page {r['id']}")),
                )
        monkeypatch.setattr(
            f"ccandle.sync.delete_dead_pages.get_all_ids_in_pages",
            lambda: [r["id"] for r in rows],
        )

    def remaining_ids():
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(f"SELECT id FROM {TABLE_PAGES}").fetchall()
        return {row[0] for row in rows}

    return SimpleNamespace(
        seed=seed,
        remaining_ids=remaining_ids,
        render_table_calls=render_table_calls,
    )


def make_ids(n, prefix):
    return [f"{prefix}{i}" for i in range(n)]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_empty_cloud_ids_returns_early_and_touches_nothing(local_pages_db, monkeypatch):
    local_pages_db.seed([{"id": "A"}, {"id": "B"}])

    def fail_if_called():
        raise AssertionError(
            "get_all_ids_in_pages() should not be called when all_cloud_ids is empty "
            "-- the empty-cloud guard must return before touching local state at all."
        )

    monkeypatch.setattr(f"ccandle.sync.delete_dead_pages.get_all_ids_in_pages", fail_if_called)

    delete_dead_db_pages([])
    delete_dead_db_pages(None)

    assert local_pages_db.remaining_ids() == {"A", "B"}
    assert local_pages_db.render_table_calls == []


def test_nothing_deleted_when_local_matches_cloud(local_pages_db):
    local_pages_db.seed([{"id": "A"}, {"id": "B"}])

    delete_dead_db_pages(["A", "B"])

    assert local_pages_db.remaining_ids() == {"A", "B"}
    assert local_pages_db.render_table_calls == []


def test_deletes_only_pages_absent_from_cloud(local_pages_db):
    local_pages_db.seed([
        {"id": "A", "space_id": "S1", "title": "Alpha"},
        {"id": "B", "space_id": "S1", "title": "Bravo"},  # stale: not in cloud
        {"id": "C", "space_id": "S2", "title": "Charlie"},
    ])

    delete_dead_db_pages(["A", "C"])

    assert local_pages_db.remaining_ids() == {"A", "C"}
    assert len(local_pages_db.render_table_calls) == 1
    dead_pages = local_pages_db.render_table_calls[0]
    assert dead_pages == [{"id": "B", "space_id": "S1", "title": "Bravo"}]


def test_deletes_all_local_pages_when_none_are_in_cloud(local_pages_db):
    # Cloud id list is non-empty (so the early-return guard does NOT fire)
    # but shares nothing with the local table -- a genuine "everything here
    # is stale" case, distinct from an accidentally-empty cloud response.
    local_pages_db.seed([{"id": "A"}, {"id": "B"}])

    delete_dead_db_pages(["completely-unrelated-cloud-page"])

    assert local_pages_db.remaining_ids() == set()


def test_single_page_deletion_does_not_break_sql_placeholder_list(local_pages_db):
    # Regression guard for the ",".join(["?"] * len(to_delete)) placeholder
    # construction at len == 1 (easy off-by-one spot for "?," vs "?").
    local_pages_db.seed([{"id": "A"}, {"id": "B"}])

    delete_dead_db_pages(["A"])

    assert local_pages_db.remaining_ids() == {"A"}


def test_mass_deletion_warning_fires_above_threshold(local_pages_db, capsys):
    # Threshold is: to_delete > 50 AND to_delete > local_count / 10.
    # 100 local pages, 51 stale -> 51 > 50 and 51 > 10: both true.
    local_ids = make_ids(100, "local-")
    local_pages_db.seed([{"id": pid} for pid in local_ids])
    surviving_ids = local_ids[:49]  # 49 remain in cloud, 51 are stale

    delete_dead_db_pages(surviving_ids)

    assert len(local_pages_db.remaining_ids()) == 49
    captured = capsys.readouterr()
    assert HINT_MANY_FOR_DELETION in captured.out


def test_mass_deletion_warning_does_not_fire_below_ratio(local_pages_db, capsys):
    # Enough deletions to clear the absolute "> 50" bar, but not the
    # relative ">10% of local" bar: 1000 local pages, 60 stale.
    # 60 > 50 is True, but 60 > 100 (1000/10) is False.
    local_ids = make_ids(1000, "local-")
    local_pages_db.seed([{"id": pid} for pid in local_ids])
    surviving_ids = local_ids[:940]

    delete_dead_db_pages(surviving_ids)

    assert len(local_pages_db.remaining_ids()) == 940
    captured = capsys.readouterr()
    assert HINT_MANY_FOR_DELETION not in captured.out


def test_small_deletion_does_not_warn(local_pages_db, capsys):
    local_pages_db.seed([{"id": "A"}, {"id": "B"}, {"id": "C"}])

    delete_dead_db_pages(["A"])  # B and C are stale, well under any threshold

    captured = capsys.readouterr()
    assert HINT_MANY_FOR_DELETION not in captured.out