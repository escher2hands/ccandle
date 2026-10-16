# Shared fixtures for the processing-stage tests (plain text, title index, basic metadata).

import json
import sqlite3

import pytest

from ccandle.config.config_db import TABLE_PAGES
from ccandle.spaces import space_utils

# Two configured spaces. Ids are strings, as Confluence returns them.
SPACES = [
    {"id": "100", "key": "DOCS", "name": "Docs"},
    {"id": "200", "key": "ENG", "name": "Engineering"},
]

# Minimal schema: only the columns the processing steps read or write.
# If ccandle has a real schema-creation function, swap it in here so schema drift is caught.
PAGE_SCHEMA = f"""
CREATE TABLE {TABLE_PAGES} (
    id            TEXT PRIMARY KEY,
    title         TEXT,
    space_id      TEXT,
    html          TEXT,
    plain_text    TEXT,
    word_count    INTEGER,
    links_list    TEXT,
    link_count    INTEGER,
    image_count   INTEGER,
    lead_para     TEXT,
    has_link_tree INTEGER,
    eval_notes    TEXT
)
"""


@pytest.fixture(autouse=True)
def configured_spaces(monkeypatch):
    """Replace the configured-spaces lookup so tests never read real user config.

    Patched at the source (space_utils.list_configured_spaces), not in each consumer.
    dict_space_keys_by_id is therefore the REAL function, and every module that builds
    on it is covered no matter how it imports it. Autouse, so no test can forget it.
    A test can override by calling monkeypatch.setattr on the same target again.
    """
    spaces = [dict(s) for s in SPACES]
    monkeypatch.setattr(space_utils, "list_configured_spaces", lambda: spaces)
    return spaces


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "ccandle_test.db"
    with sqlite3.connect(path) as conn:
        conn.execute(PAGE_SCHEMA)
    return path


@pytest.fixture
def make_db(tmp_path):
    """Factory for extra, independent DBs (e.g. to compare insert orders)."""
    counter = iter(range(1000))

    def _make(pages):
        path = tmp_path / f"extra_{next(counter)}.db"
        with sqlite3.connect(path) as conn:
            conn.execute(PAGE_SCHEMA)
            for p in pages:
                conn.execute(
                    f"INSERT INTO {TABLE_PAGES} (id, title, space_id, html) VALUES (?, ?, ?, ?)",
                    (str(p["id"]), p.get("title"), p.get("space_id", "100"), p.get("html", "")),
                )
        return path
    return _make


@pytest.fixture
def add_page(db_path):
    def _add(pid, title=None, html="", space_id="100", *, plain_text=None, word_count=None):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE_PAGES} (id, title, space_id, html, plain_text, word_count) "
                f"VALUES (?, ?, ?, ?, ?, ?)",
                (str(pid), title, str(space_id), html, plain_text, word_count),
            )
        return str(pid)
    return _add


@pytest.fixture
def read_page(db_path):
    """Plain-text step columns only (what parse_to_plain_text owns)."""
    def _read(pid):
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                f"SELECT plain_text, word_count, links_list FROM {TABLE_PAGES} WHERE id = ?", (str(pid),)
            ).fetchone()
        text, word_count, links = row
        return {"text": text, "word_count": word_count, "links": json.loads(links) if links is not None else None}
    return _read


@pytest.fixture
def read_row(db_path):
    """Every column of one page, as a dict."""
    def _read(pid):
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(f"SELECT * FROM {TABLE_PAGES} WHERE id = ?", (str(pid),)).fetchone()
        return dict(row) if row else None
    return _read


@pytest.fixture
def read_all_rows(db_path):
    def _all():
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(f"SELECT * FROM {TABLE_PAGES} ORDER BY id").fetchall()
        return {r["id"]: dict(r) for r in rows}
    return _all