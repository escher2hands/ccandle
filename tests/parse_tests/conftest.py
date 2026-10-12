import json
import sqlite3

import pytest

from ccandle.config.config_db import TABLE_PAGES
from ccandle.pages.parsing import parse_to_plain_text

# Two configured spaces. Ids are strings, as Confluence returns them.
SPACES = [
    {"id": "100", "key": "DOCS", "name": "Docs"},
    {"id": "200", "key": "ENG", "name": "Engineering"},
]


@pytest.fixture
def configured_spaces(monkeypatch):
    """Replace the configured-spaces lookup so tests never read real user config."""
    monkeypatch.setattr(parse_to_plain_text, "list_configured_spaces", lambda: SPACES)
    return SPACES


@pytest.fixture
def db_path(tmp_path):
    """A throwaway SQLite DB containing only the pages columns parse_to_plain_text touches.
    If ccandle has a real schema-creation function, swap it in here so schema drift is caught."""
    path = tmp_path / "ccandle_test.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            f"CREATE TABLE {TABLE_PAGES} ("
            "id TEXT PRIMARY KEY, title TEXT, space_id TEXT, html TEXT, "
            "plain_text TEXT, word_count INTEGER, links_list TEXT)"
        )
    return path


@pytest.fixture
def add_page(db_path):
    def _add(pid, title, html, space_id="100"):
        with sqlite3.connect(db_path) as conn:
            conn.execute(
                f"INSERT INTO {TABLE_PAGES} (id, title, space_id, html) VALUES (?, ?, ?, ?)",
                (str(pid), title, space_id, html),
            )
    return _add


@pytest.fixture
def read_page(db_path):
    def _read(pid):
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                f"SELECT plain_text, word_count, links_list FROM {TABLE_PAGES} WHERE id = ?", (str(pid),)
            ).fetchone()
        text, word_count, links = row
        return {"text": text, "word_count": word_count, "links": json.loads(links) if links is not None else None}
    return _read