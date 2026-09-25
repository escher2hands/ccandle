"""
Tests for ccandle's labels module.

ASSUMPTION: the module under test lives at ccandle/labels/labels.py and is
importable as `ccandle.labels.labels`. Adjust the import below if yours
lives elsewhere.

Run with:
    pytest test_labels.py -v
"""
import datetime
import json
import sqlite3

import pytest

import ccandle.labels.scrape_labels as labels_module
from ccandle.labels.scrape_labels import (
    scrape_labels,
    _sync_label_names_from_confluence,
    _store_synced_labels,
    _sync_labels_to_pages,
    _store_page_label_mapping,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """
    Point PATH_DB/TABLE_LABELS/TABLE_PAGES at a throwaway sqlite file.

    Now that these are imported at module top-level (rather than inline
    inside each function), patching attributes directly on labels_module is
    enough -- no need to reach into ccandle.config.config_db separately.
    """
    db_path = tmp_path / "test_ccandle.db"
    monkeypatch.setattr(labels_module, "PATH_DB", str(db_path))
    monkeypatch.setattr(labels_module, "TABLE_LABELS", "labels")
    monkeypatch.setattr(labels_module, "TABLE_PAGES", "pages")

    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE pages (id TEXT PRIMARY KEY, labels TEXT)")
        conn.commit()
    # The labels table is intentionally NOT created here -- create_table_hard
    # is responsible for creating it fresh on every single sync (see
    # fake_create_table_hard below), and we want tests to exercise that
    # real behavior rather than assume it.

    return db_path


@pytest.fixture
def fake_create_table_hard(monkeypatch, test_db):
    """
    Stand-in for create_table_hard that actually drops and recreates the
    table, so tests can verify the real "wipe old data on every resync"
    behavior instead of assuming it. We don't depend on the real
    SCHEMA_LABELS definition here -- just the columns _store_synced_labels
    actually inserts into.
    """
    def _fake(table_name, schema):
        with sqlite3.connect(test_db) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.execute(f"""
                CREATE TABLE {table_name} (
                    id TEXT PRIMARY KEY,
                    label TEXT,
                    space_id TEXT,
                    retrieved_at TEXT
                )
            """)
            conn.commit()

    monkeypatch.setattr(labels_module, "create_table_hard", _fake)
    return _fake


# ---------------------------------------------------------------------------
# _store_synced_labels
# ---------------------------------------------------------------------------

class TestStoreSyncedLabels:
    def test_inserts_records(self, test_db, fake_create_table_hard):
        records = [
            {"id": "L1", "label": "onboarding", "space_id": "SPACE1", "retrieved_at": "2026-01-01T00:00:00+00:00"},
            {"id": "L2", "label": "roadmap", "space_id": "SPACE1", "retrieved_at": "2026-01-01T00:00:00+00:00"},
        ]
        _store_synced_labels(records)

        with sqlite3.connect(test_db) as conn:
            rows = conn.execute("SELECT id, label, space_id FROM labels ORDER BY id").fetchall()
        assert rows == [("L1", "onboarding", "SPACE1"), ("L2", "roadmap", "SPACE1")]

    def test_full_resync_replaces_old_data_entirely(self, test_db, fake_create_table_hard):
        _store_synced_labels([{"id": "L1", "label": "old-label", "space_id": "SPACE1", "retrieved_at": "t1"}])
        _store_synced_labels([{"id": "L2", "label": "new-label", "space_id": "SPACE1", "retrieved_at": "t2"}])

        with sqlite3.connect(test_db) as conn:
            rows = conn.execute("SELECT id, label FROM labels").fetchall()
        # L1 from the first sync must be gone entirely, not left sitting
        # alongside L2 -- create_table_hard rebuilds the table from scratch
        # on every call, it doesn't accumulate across syncs.
        assert rows == [("L2", "new-label")]

    def test_duplicate_id_within_one_sync_keeps_first_occurrence(self, test_db, fake_create_table_hard):
        """
        Pins down the current ON CONFLICT(id) DO NOTHING behavior: if the
        same label id appears twice in one sync, only the space_id from
        whichever record was processed first survives -- the second is
        silently dropped, not merged or overwritten.
        """
        records = [
            {"id": "L1", "label": "onboarding", "space_id": "SPACE_A", "retrieved_at": "t1"},
            {"id": "L1", "label": "onboarding", "space_id": "SPACE_B", "retrieved_at": "t2"},
        ]
        _store_synced_labels(records)

        with sqlite3.connect(test_db) as conn:
            row = conn.execute("SELECT space_id FROM labels WHERE id = ?", ("L1",)).fetchone()
        assert row == ("SPACE_A",)


# ---------------------------------------------------------------------------
# _sync_label_names_from_confluence
# ---------------------------------------------------------------------------

class TestSyncLabelNamesFromConfluence:
    def test_retrieved_at_is_stored_as_an_isoformat_string(
        self, test_db, fake_create_table_hard, monkeypatch
    ):
        # Regression test for the datetime-object-vs-isoformat-string fix:
        # retrieved_at should now be a plain ISO-8601 string, not something
        # that only round-trips correctly by accident of sqlite3's
        # (deprecated) default datetime adapter.
        monkeypatch.setattr(labels_module, "list_configured_space_ids", lambda: ["SPACE1"])
        monkeypatch.setattr(
            labels_module, "request_labels_for_space",
            lambda space_id: [{"id": "L1", "label": "onboarding"}],
        )

        _sync_label_names_from_confluence()

        with sqlite3.connect(test_db) as conn:
            row = conn.execute("SELECT retrieved_at FROM labels WHERE id = ?", ("L1",)).fetchone()
        assert isinstance(row[0], str)
        datetime.datetime.fromisoformat(row[0])  # raises ValueError if not a valid ISO string

    def test_aggregates_labels_across_multiple_spaces(
        self, test_db, fake_create_table_hard, monkeypatch
    ):
        monkeypatch.setattr(
            labels_module, "list_configured_space_ids", lambda: ["SPACE1", "SPACE2"]
        )

        def fake_request_labels_for_space(space_id):
            return {
                "SPACE1": [{"id": "L1", "label": "onboarding"}],
                "SPACE2": [{"id": "L2", "label": "roadmap"}],
            }[space_id]

        monkeypatch.setattr(
            labels_module, "request_labels_for_space", fake_request_labels_for_space
        )

        result = _sync_label_names_from_confluence()

        assert {r["id"] for r in result} == {"L1", "L2"}
        with sqlite3.connect(test_db) as conn:
            stored_ids = {row[0] for row in conn.execute("SELECT id FROM labels")}
        assert stored_ids == {"L1", "L2"}


# ---------------------------------------------------------------------------
# _store_page_label_mapping
# ---------------------------------------------------------------------------

class TestStorePageLabelMapping:
    def test_labels_are_stored_sorted_for_deterministic_json(self, test_db):
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", "[]"))
            conn.commit()

        # Insertion order into the set is deliberately not alphabetical.
        _store_page_label_mapping({"1": {"zeta", "alpha", "mid"}})

        with sqlite3.connect(test_db) as conn:
            row = conn.execute("SELECT labels FROM pages WHERE id = ?", ("1",)).fetchone()
        assert json.loads(row[0]) == ["alpha", "mid", "zeta"]

    def test_pages_missing_from_the_new_mapping_are_wiped_to_empty(self, test_db):
        """
        Documents the full-refresh design: every page's labels column is
        reset to '[]' before the fresh mapping is applied, so any page not
        present in page_to_labels this round ends up with no labels, even
        if it had some before. Correct as long as page_to_labels is a
        complete picture for the run -- see the next test for the risk in
        the other direction.
        """
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", json.dumps(["old-label"])))
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("2", json.dumps(["keep-me"])))
            conn.commit()

        _store_page_label_mapping({"2": {"keep-me"}})

        with sqlite3.connect(test_db) as conn:
            rows = dict(conn.execute("SELECT id, labels FROM pages").fetchall())
        assert json.loads(rows["1"]) == []
        assert json.loads(rows["2"]) == ["keep-me"]

    def test_pid_not_yet_present_in_pages_table_is_silently_dropped(self, test_db):
        """
        _store_page_label_mapping only ever UPDATEs -- it never INSERTs. If
        a pid shows up in page_to_labels that hasn't been ingested into the
        pages table yet (a brand-new page, a space still mid-sync), the
        UPDATE affects zero rows and that page's labels are discarded with
        no error and no trace that anything was skipped.
        """
        # pages table intentionally left empty
        _store_page_label_mapping({"unknown-pid": {"onboarding"}})

        with sqlite3.connect(test_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        assert count == 0  # no row created, and no exception raised either

    def test_multiple_labels_for_one_page_combine_correctly(self, test_db):
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", "[]"))
            conn.commit()

        _store_page_label_mapping({"1": {"onboarding", "roadmap"}})

        with sqlite3.connect(test_db) as conn:
            row = conn.execute("SELECT labels FROM pages WHERE id = ?", ("1",)).fetchone()
        assert json.loads(row[0]) == ["onboarding", "roadmap"]


# ---------------------------------------------------------------------------
# _sync_labels_to_pages
# ---------------------------------------------------------------------------

class TestSyncLabelsToPages:
    def test_dedups_duplicate_pids_returned_for_the_same_label(self, test_db, monkeypatch):
        monkeypatch.setattr(
            labels_module, "get_all_labels_with_ids",
            lambda: [{"id": "L1", "label": "onboarding"}],
        )
        monkeypatch.setattr(
            labels_module, "request_pages_for_label",
            lambda label_id: ["1", "1", "1"],  # same pid returned three times
        )
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", "[]"))
            conn.commit()

        result = _sync_labels_to_pages(quiet=True)

        assert result == {"1": {"onboarding"}}
        with sqlite3.connect(test_db) as conn:
            row = conn.execute("SELECT labels FROM pages WHERE id = ?", ("1",)).fetchone()
        assert json.loads(row[0]) == ["onboarding"]

    def test_combines_labels_from_multiple_label_records_for_same_page(self, test_db, monkeypatch):
        monkeypatch.setattr(
            labels_module, "get_all_labels_with_ids",
            lambda: [{"id": "L1", "label": "onboarding"}, {"id": "L2", "label": "roadmap"}],
        )
        monkeypatch.setattr(
            labels_module, "request_pages_for_label",
            lambda label_id: ["1"],  # both labels apply to the same page
        )
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", "[]"))
            conn.commit()

        result = _sync_labels_to_pages(quiet=True)

        assert result == {"1": {"onboarding", "roadmap"}}


# ---------------------------------------------------------------------------
# scrape_labels -- full orchestration
# ---------------------------------------------------------------------------

class TestScrapeLabels:
    def test_runs_both_sync_steps_end_to_end(self, test_db, fake_create_table_hard, monkeypatch):
        monkeypatch.setattr(labels_module, "list_configured_space_ids", lambda: ["SPACE1"])
        monkeypatch.setattr(
            labels_module, "request_labels_for_space",
            lambda space_id: [{"id": "L1", "label": "onboarding"}],
        )
        monkeypatch.setattr(
            labels_module, "get_all_labels_with_ids",
            lambda: [{"id": "L1", "label": "onboarding"}],
        )
        monkeypatch.setattr(
            labels_module, "request_pages_for_label",
            lambda label_id: ["1"],
        )
        with sqlite3.connect(test_db) as conn:
            conn.execute("INSERT INTO pages (id, labels) VALUES (?, ?)", ("1", "[]"))
            conn.commit()

        scrape_labels(quiet=True)

        with sqlite3.connect(test_db) as conn:
            label_row = conn.execute("SELECT label, space_id FROM labels").fetchone()
            page_row = conn.execute("SELECT labels FROM pages WHERE id = ?", ("1",)).fetchone()
        assert label_row == ("onboarding", "SPACE1")
        assert json.loads(page_row[0]) == ["onboarding"]