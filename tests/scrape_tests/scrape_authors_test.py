"""
Tests for ccandle's authors module.

ASSUMPTION: the module under test lives at ccandle/authors/authors.py and is
importable as `ccandle.authors.authors`. If your file lives elsewhere, just
change the import below -- everything else references functions through
`authors_module`, so a single import fix is all that's needed.

Run with:
    pytest test_authors.py -v
"""
import json
import sqlite3

import pytest

import ccandle.authors.scrape_authors as authors_module
from ccandle.authors.scrape_authors import (
    squash_to_interesting,
    normalize_author_name,
    _normalize_weird_chars,
    get_unique_authors,
    get_name_from_author_id,
    _fetch_and_store_author_metadata,
    _store_author_history_for_pages,
    scrape_authors,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db(tmp_path, monkeypatch):
    """
    Point the module at a throwaway sqlite file and create both tables
    directly with the exact columns the module's own insert statements
    expect. This avoids depending on the real SCHEMA_AUTHORS definition
    (which isn't in this file) and keeps the test isolated / fast.
    """
    db_path = tmp_path / "test_ccandle.db"

    monkeypatch.setattr(authors_module, "PATH_DB", str(db_path))
    monkeypatch.setattr(authors_module, "TABLE_PAGES", "pages")
    monkeypatch.setattr(authors_module, "TABLE_AUTHORS", "authors")
    # create_table(...) is real production code that presumably builds the
    # authors table from SCHEMA_AUTHORS; we short-circuit it here since we
    # create the table ourselves below with the columns actually used.
    monkeypatch.setattr(authors_module, "create_table", lambda *a, **k: None)

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE authors (
                author_id TEXT PRIMARY KEY,
                name TEXT,
                display_name TEXT,
                email TEXT,
                name_normalized TEXT,
                last_modified TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE pages (
                id TEXT PRIMARY KEY,
                authors TEXT
            )
        """)
        conn.commit()

    return db_path


# ---------------------------------------------------------------------------
# squash_to_interesting
# ---------------------------------------------------------------------------

class TestSquashToInteresting:
    def test_short_streaks_kept_untouched(self):
        assert squash_to_interesting(["a", "b", "c"]) == ["a", "b", "c"]

    def test_streak_of_exactly_three_fully_kept(self):
        assert squash_to_interesting(["a", "a", "a"]) == ["a", "a", "a"]

    def test_streak_longer_than_three_is_truncated(self):
        assert squash_to_interesting(["a", "a", "a", "a", "a"]) == ["a", "a", "a"]

    def test_streak_resets_after_interruption(self):
        result = squash_to_interesting(["a", "a", "a", "a", "b", "a", "a", "a", "a"])
        assert result == ["a", "a", "a", "b", "a", "a", "a"]

    def test_empty_list(self):
        assert squash_to_interesting([]) == []

    def test_single_item(self):
        assert squash_to_interesting(["a"]) == ["a"]


# ---------------------------------------------------------------------------
# _normalize_weird_chars -- direct regression tests for the digraph bug
# ---------------------------------------------------------------------------

class TestNormalizeWeirdChars:
    def test_digraph_replacements_are_applied_not_dropped(self):
        # This is the regression test for the original bug: the membership
        # check used to compare the *replacement string* ("ue", "ss", ...)
        # against ALLOWED_CHARS (a set of single characters), so digraphs
        # were silently deleted instead of substituted.
        assert _normalize_weird_chars("ü") == "ue"
        assert _normalize_weird_chars("ß") == "ss"
        assert _normalize_weird_chars("Müller") == "Mueller"

    def test_single_char_replacements_still_work(self):
        assert _normalize_weird_chars("café") == "cafe"
        assert _normalize_weird_chars("garçon") == "garcon"

    def test_polish_diacritics_expand_correctly(self):
        assert _normalize_weird_chars("żźłńśąę") == "zzlnsae"

    def test_bracket_and_punctuation_chars_are_removed(self):
        assert _normalize_weird_chars("(Team)!") == "Team"

# ---------------------------------------------------------------------------
# normalize_author_name
# ---------------------------------------------------------------------------

class TestNormalizeAuthorName:
    def test_empty_or_none_returns_empty_string(self):
        assert normalize_author_name("") == ""
        assert normalize_author_name(None) == ""

    def test_single_name_no_surname(self):
        assert normalize_author_name("Madonna") == "madonna"

    def test_given_surname_space_format(self):
        assert normalize_author_name("Hans Muller") == "hans:muller"

    def test_surname_comma_given_format_matches_space_format(self):
        assert normalize_author_name("Muller, Hans") == "hans:muller"

    def test_umlaut_and_eszett_expansion(self):
        assert normalize_author_name("Müller") == "mueller"
        assert normalize_author_name("Straße") == "strasse"

    def test_umlaut_expansion_in_both_given_and_surname(self):
        assert normalize_author_name("Müller Königsberg") == "mueller:koenigsberg"

    def test_accented_chars_collapse_to_ascii(self):
        assert normalize_author_name("François Petit") == "francois:petit"

    def test_apostrophe_and_hyphen_do_not_survive_to_final_output(self):
        """
        ALLOWED_CHARS permits space/hyphen/apostrophe through the character
        filter in _normalize_weird_chars, but normalize_author_name then
        runs _STRIP_NON_ALPHA (a \\W+ regex) over the result, which strips
        those same characters right back out. So including them in
        ALLOWED_CHARS currently has no effect on the final key -- it's
        dead configuration unless the regex step changes too.
        """
        assert normalize_author_name("Jean-Pierre O'Brien") == "jeanpierre:obrien"

    def test_multi_word_surname_loses_internal_spaces(self):
        # Same \W+ effect as above: a multi-word surname collapses into a
        # single token rather than staying space-separated.
        assert normalize_author_name("Anna Van Der Berg") == "anna:vanderberg"

    def test_debug_flag_does_not_change_output(self):
        # `debug` is currently unused by the function body; this just pins
        # down that passing it doesn't alter behavior today.
        assert normalize_author_name("Hans Muller", debug=True) == "hans:muller"


# ---------------------------------------------------------------------------
# get_unique_authors
# ---------------------------------------------------------------------------

class TestGetUniqueAuthors:
    def test_recent_authors_arg_bypasses_db_entirely(self):
        # No test_db fixture used here on purpose: this path must not touch
        # sqlite at all when recent_authors is provided.
        result = get_unique_authors([["a", "b"], ["b", "c"]])
        assert set(result) == {"a", "b", "c"}

    def test_recent_authors_empty_list_of_lists(self):
        assert get_unique_authors([[], []]) == []

    def test_mode_id_reads_from_authors_table(self, test_db):
        with sqlite3.connect(test_db) as conn:
            conn.execute(
                "INSERT INTO authors (author_id, name_normalized) VALUES (?, ?)",
                ("acc1", "anna:admin"),
            )
            conn.execute(
                "INSERT INTO authors (author_id, name_normalized) VALUES (?, ?)",
                ("acc2", "bob:builder"),
            )
            conn.commit()

        result = get_unique_authors(mode="id")
        assert set(result) == {"acc1", "acc2"}

    def test_mode_name_reads_from_pages_table(self, test_db):
        with sqlite3.connect(test_db) as conn:
            conn.execute(
                "INSERT INTO pages (id, authors) VALUES (?, ?)",
                ("1", json.dumps(["anna:admin", "bob:builder"])),
            )
            conn.execute(
                "INSERT INTO pages (id, authors) VALUES (?, ?)",
                ("2", json.dumps(["bob:builder"])),
            )
            conn.commit()

        result = get_unique_authors(mode="name")
        assert set(result) == {"anna:admin", "bob:builder"}

    def test_invalid_mode_raises(self, test_db):
        with pytest.raises(ValueError):
            get_unique_authors(mode="bogus")


# ---------------------------------------------------------------------------
# _fetch_and_store_author_metadata
# ---------------------------------------------------------------------------

class TestFetchAndStoreAuthorMetadata:
    def test_empty_id_list_short_circuits(self, test_db, monkeypatch):
        called = {"value": False}
        monkeypatch.setattr(
            authors_module, "request_users_metadata",
            lambda ids: called.update(value=True) or [],
        )
        result = _fetch_and_store_author_metadata([])
        assert result == {}
        assert called["value"] is False

    def test_fetches_normalizes_and_stores(self, test_db, monkeypatch):
        raw_metadata = [
            {"accountId": "acc1", "publicName": "Hans Müller",
             "displayName": "Hans M.", "email": "hans@x.com"},
            {"accountId": "acc2", "publicName": "Jane Doe",
             "displayName": "Jane D.", "email": "jane@x.com"},
        ]
        monkeypatch.setattr(
            authors_module, "request_users_metadata", lambda ids: raw_metadata
        )

        result = _fetch_and_store_author_metadata(["acc1", "acc2"])

        assert result == {"acc1": "hans:mueller", "acc2": "jane:doe"}

        with sqlite3.connect(test_db) as conn:
            rows = dict(conn.execute(
                "SELECT author_id, name_normalized FROM authors"
            ).fetchall())
        assert rows == {"acc1": "hans:mueller", "acc2": "jane:doe"}


# ---------------------------------------------------------------------------
# _store_author_history_for_pages -- upsert behavior
# ---------------------------------------------------------------------------

class TestStoreAuthorHistoryForPages:
    def test_insert_then_update_on_conflict(self, test_db):
        _store_author_history_for_pages(
            [{"id": "1", "authors": ["anna:admin"]}]
        )
        _store_author_history_for_pages(
            [{"id": "1", "authors": ["anna:admin", "bob:builder"]}]
        )

        with sqlite3.connect(test_db) as conn:
            row = conn.execute(
                "SELECT authors FROM pages WHERE id = ?", ("1",)
            ).fetchone()
        assert json.loads(row[0]) == ["anna:admin", "bob:builder"]

    def test_multiple_pages_in_one_call(self, test_db):
        _store_author_history_for_pages([
            {"id": "1", "authors": ["anna:admin"]},
            {"id": "2", "authors": ["bob:builder"]},
        ])
        with sqlite3.connect(test_db) as conn:
            count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
        assert count == 2


# ---------------------------------------------------------------------------
# get_name_from_author_id
# ---------------------------------------------------------------------------

class TestGetNameFromAuthorId:
    def test_found(self, test_db):
        with sqlite3.connect(test_db) as conn:
            conn.execute(
                "INSERT INTO authors (author_id, name_normalized) VALUES (?, ?)",
                ("acc1", "anna:admin"),
            )
            conn.commit()
        assert get_name_from_author_id("acc1") == "anna:admin"

    def test_not_found_returns_none(self, test_db):
        assert get_name_from_author_id("nonexistent") is None


# ---------------------------------------------------------------------------
# scrape_authors -- integration test across multiple batches
# ---------------------------------------------------------------------------

class TestScrapeAuthors:
    def test_accumulates_results_across_batches_and_persists_correctly(
        self, test_db, monkeypatch
    ):
        # Editors per page, keyed by pid as a string (endpoint building
        # uses str(pid), so we match on that substring below).
        page_editors = {
            "1": ["accA", "accA", "accA", "accA", "accB"],  # 4-streak -> squashed to 3
            "2": ["accB"],
            "3": ["accA", "accA"],
        }
        accounts = {
            "accA": {"accountId": "accA", "publicName": "Anna Admin",
                     "displayName": "Anna", "email": "anna@x.com"},
            "accB": {"accountId": "accB", "publicName": "Bob Builder",
                     "displayName": "Bob", "email": "bob@x.com"},
        }

        def fake_request_paginated_results(endpoint, limit=200):
            for pid_str, editors in page_editors.items():
                if f"/{pid_str}/" in endpoint:
                    return [{"authorId": aid} for aid in editors]
            raise AssertionError(f"Unexpected endpoint: {endpoint}")

        def fake_request_users_metadata(ids):
            return [accounts[i] for i in ids]

        def fake_chunked(pids, size):
            # Force two batches regardless of BATCH_SIZE, specifically to
            # exercise the cumulative_results accumulation fix.
            return [pids[:2], pids[2:]]

        monkeypatch.setattr(authors_module, "get_all_ids_in_pages", lambda: [1, 2, 3])
        monkeypatch.setattr(authors_module, "chunked", fake_chunked)
        monkeypatch.setattr(
            authors_module, "request_paginated_results", fake_request_paginated_results
        )
        monkeypatch.setattr(
            authors_module, "request_users_metadata", fake_request_users_metadata
        )

        result = scrape_authors(quiet=True)

        # The accumulation fix: results from BOTH batches must be present,
        # not just the last one.
        assert len(result) == 3
        result_by_id = {r["id"]: r["authors"] for r in result}
        assert result_by_id[1] == ["anna:admin", "anna:admin", "anna:admin", "bob:builder"]
        assert result_by_id[2] == ["bob:builder"]
        assert result_by_id[3] == ["anna:admin", "anna:admin"]

        # And it should actually be persisted, not just returned in memory.
        with sqlite3.connect(test_db) as conn:
            page_count = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
            author_ids = {
                row[0] for row in conn.execute("SELECT author_id FROM authors")
            }
        assert page_count == 3
        assert author_ids == {"accA", "accB"}