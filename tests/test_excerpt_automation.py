"""
Minimal tests for insert_excerpt_include_via_api / remove_excerpt_include_via_api.

Focus (per requirements):
  1. Transform: insert() turns WO html into WITH-equivalent html;
     remove() turns WITH html into exactly WO html.
  2. Idempotency: calling insert() twice raises (no duplicate applied);
     calling remove() twice is a no-op the second time.
  3. Reversibility: insert -> remove -> insert round-trips back to WO html.
"""
import pytest
from unittest.mock import patch
import ccandle.excerpts.excerpt_bulk_actions as em  # <-- adjust to actual module name/path
from tests.test_fixtures_excerpt_pages import *

TARGET_PID = "TARGET1"
SOURCE_PID = "SOURCE1"
TARGET_SPACE = "TEST"  # different from excerpt source's space, so the
                        # generated macro includes ri:space-key (matches fixtures)

# NOTE: the layout/table WO<->WITH fixture pairs turn out to differ by more
# than just the excerpt-include macro (e.g. an unrelated link's
# ri:version-at-save was also bumped between snapshots). Only "bare" is a
# clean pair where the sole difference is the trailing macro, so it's the
# only case where we assert byte-for-byte equality against the WO fixture.
# The other two still get full coverage via the reversibility checks (insert
# then strip reproduces the pre-insert state), which don't depend on the
# WO/WITH fixtures matching outside of the macro itself.
CASES = [
    pytest.param(
        PAGE_WO_EXCERPT_LAYOUT_ENDING, PAGE_WITH_EXCERPT_LAYOUT_ENDING,
        {
            "title": "00 - Documentation philosophy and knowledge management principles",
            "version": 6,
            "space_key": "KMBP",
            "name": "knowledge management category box",
        },
        False,
        id="layout",
    ),
    pytest.param(
        PAGE_WO_EXCERPT_TABLE_ENDING, PAGE_WITH_EXCERPT_TABLE_ENDING,
        {
            "title": "Elements of 'beautiful,' effective pages",
            "version": 9,
            "space_key": "KMBP",
            "name": "page best practices navbox",
        },
        False,
        id="table",
    ),
    pytest.param(
        PAGE_WO_EXCERPT_BARE_ENDING, PAGE_WITH_EXCERPT_BARE_ENDING,
        {
            "title": "Elements of 'beautiful,' effective pages",
            "version": 9,
            "space_key": "KMBP",
            "name": "page best practices navbox",
        },
        True,
        id="bare",
    ),
]


class FakeDB:
    """Tiny in-memory stand-in for the sqlite-backed page store."""

    def __init__(self, html, version=1, title="Target Page", space_key=TARGET_SPACE):
        self.pid = TARGET_PID
        self.title = title
        self.version = version
        self.space_key = space_key
        self.html = html

    def page_data(self):
        return {
            "pid": self.pid,
            "title": self.title,
            "version": self.version,
            "space_key": self.space_key,
            "html": self.html,
        }


def _patched(db, source_data, has_include_flags):
    """
    Context manager stack patching the module's DB/network boundary so we can
    exercise insert/remove logic in isolation.

    has_include_flags: mutable dict the test can flip to simulate whether the
    page "already has" a navbox include (mirrors _already_has_an_excerpt_include).
    """

    def fake_extract_excerpt_data(pid):
        return dict(source_data)

    def fake_extract_relevant_page_data(pid):
        return db.page_data()

    def fake_request_put_page(target_page_data, new_html):
        # Mirrors real behavior: insert_/remove_excerpt_include_via_api treat
        # the returned 'version' as the *pre-save* version and add 1 to it
        # themselves via _increment_page_version_and_html_in_db -> update_field.
        # So we must NOT bump db.version here, just report the current one.
        return {
            "status": "success",
            "http_status": 200,
            "version": db.version,
            "html": new_html,
        }

    def fake_update_field(pid, field, value):
        if field == "version":
            db.version = value
        elif field == "html":
            db.html = value

    def fake_already_has_include(html_or_pid, navbox_only=False):
        if has_include_flags.get("navbox", False):
            return {"name": "existing navbox"}
        return False

    return (
        patch.object(em, "extract_excerpt_data", side_effect=fake_extract_excerpt_data),
        patch.object(em, "_extract_relevant_page_data", side_effect=fake_extract_relevant_page_data),
        patch.object(em, "request_put_page", side_effect=fake_request_put_page),
        patch.object(em, "update_field", side_effect=fake_update_field),
        patch.object(em, "_already_has_an_excerpt_include", side_effect=fake_already_has_include),
    )


def _apply(patches):
    for p in patches:
        p.start()


def _stop(patches):
    for p in patches:
        p.stop()


@pytest.mark.parametrize("wo_html, with_html, source_data, exact_pair", CASES)
def test_remove_produces_exact_wo_html(wo_html, with_html, source_data, exact_pair):
    """remove() on WITH html should yield exactly the WO html (ids in the
    fixtures are fixed, so this is an exact match, not just structural)."""
    db = FakeDB(with_html, version=5)
    patches = _patched(db, source_data, {"navbox": True})
    _apply(patches)
    try:
        result = em.remove_excerpt_include_via_api(TARGET_PID)
    finally:
        _stop(patches)

    assert result["status"] == "success"
    assert "excerpt-include" not in db.html
    if exact_pair:
        assert db.html == wo_html
    assert db.version == 6


@pytest.mark.parametrize("wo_html, with_html, source_data, exact_pair", CASES)
def test_insert_is_reversible_to_wo_html(wo_html, with_html, source_data, exact_pair):
    """insert() on WO html, when its inserted macro is stripped back out,
    should reproduce the WO html exactly (macro ids are randomly generated
    on insert, so we can't compare directly to the WITH fixture)."""
    db = FakeDB(wo_html, version=1)
    patches = _patched(db, source_data, {"navbox": False})
    _apply(patches)
    try:
        result = em.insert_excerpt_include_via_api(SOURCE_PID, TARGET_PID)
    finally:
        _stop(patches)

    assert result["status"] == "success"
    assert db.version == 2
    assert db.html != wo_html  # something was inserted

    # The inserted macro carries the right source page identity.
    assert source_data["title"] in db.html
    assert f'ri:version-at-save="{source_data["version"]}"' in db.html
    assert source_data["name"] in db.html
    assert f'ri:space-key="{source_data["space_key"]}"' in db.html

    # Stripping the include back out reproduces the pre-insert WO html
    # exactly -- this is what "reversible" means and holds regardless of
    # whether the WO/WITH fixtures happen to match outside of the macro.
    assert em.strip_excerpt_includes(db.html) == wo_html


@pytest.mark.parametrize("wo_html, with_html, source_data, exact_pair", CASES)
def test_insert_is_idempotent(wo_html, with_html, source_data, exact_pair):
    """A second insert() on a page that already has a navbox include must
    refuse (no duplicate macro gets added)."""
    db = FakeDB(wo_html, version=1)
    flags = {"navbox": False}
    patches = _patched(db, source_data, flags)
    _apply(patches)
    try:
        em.insert_excerpt_include_via_api(SOURCE_PID, TARGET_PID)
        html_after_first_insert = db.html
        version_after_first_insert = db.version

        flags["navbox"] = True  # now simulate that the page has one, as it would
        with pytest.raises(ValueError):
            em.insert_excerpt_include_via_api(SOURCE_PID, TARGET_PID)
    finally:
        _stop(patches)

    # nothing changed as a result of the rejected second call
    assert db.html == html_after_first_insert
    assert db.version == version_after_first_insert


@pytest.mark.parametrize("wo_html, with_html, source_data, exact_pair", CASES)
def test_remove_is_idempotent(wo_html, with_html, source_data, exact_pair):
    """A second remove() on a page with no include macro should be a
    content no-op (stripping is safe to repeat)."""
    db = FakeDB(with_html, version=5)
    patches = _patched(db, source_data, {"navbox": True})
    _apply(patches)
    try:
        em.remove_excerpt_include_via_api(TARGET_PID)
        html_after_first_remove = db.html

        em.remove_excerpt_include_via_api(TARGET_PID)  # second call
    finally:
        _stop(patches)

    assert db.html == html_after_first_remove
    if exact_pair:
        assert db.html == wo_html


@pytest.mark.parametrize("wo_html, with_html, source_data, exact_pair", CASES)
def test_full_round_trip_insert_remove_insert(wo_html, with_html, source_data, exact_pair):
    """insert -> remove -> insert should land back on an equivalent state:
    stripping the final insert's macro reproduces WO html exactly, same as
    after the very first insert."""
    db = FakeDB(wo_html, version=1)
    flags = {"navbox": False}
    patches = _patched(db, source_data, flags)
    _apply(patches)
    try:
        em.insert_excerpt_include_via_api(SOURCE_PID, TARGET_PID)
        after_first_insert = em.strip_excerpt_includes(db.html)

        flags["navbox"] = True
        em.remove_excerpt_include_via_api(TARGET_PID)
        assert db.html == wo_html  # exact match after removal

        flags["navbox"] = False
        em.insert_excerpt_include_via_api(SOURCE_PID, TARGET_PID)
        after_second_insert = em.strip_excerpt_includes(db.html)
    finally:
        _stop(patches)

    assert after_first_insert == wo_html
    assert after_second_insert == wo_html
