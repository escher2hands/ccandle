"""Tests for ptp.build_title_index(path_to_db) -> (title_index, space_keys).

Replaces TestBuildTitleIndex in test_parse_to_plain_text.py (that class still calls the
old two-argument form). The `configured_spaces` autouse fixture in conftest supplies
{"100": "DOCS", "200": "ENG"} through the real dict_space_keys_by_id.
"""
import pytest

from ccandle.pages.parsing import parse_to_plain_text as ptp
from ccandle.spaces import space_utils


def test_index_is_normalized_and_skips_unindexable_pages(db_path, add_page):
    add_page("1", "Getting  Started", "<p>x</p>", space_id="100")
    add_page("2", "Design Doc", "<p>x</p>", space_id="200")
    add_page("3", "Hidden", "<p>x</p>", space_id="999")   # space not configured
    add_page("4", None, "<p>x</p>", space_id="100")        # no title
    index, _ = ptp.build_title_index(db_path)
    assert index == {("docs", "getting started"): "1", ("eng", "design doc"): "2"}


def test_returns_the_space_key_dict_alongside_the_index(db_path, add_page):
    add_page("1", "A", "<p>x</p>")
    _, space_keys = ptp.build_title_index(db_path)
    assert space_keys == {"100": "DOCS", "200": "ENG"}


def test_empty_db_gives_empty_index_but_still_returns_space_keys(db_path):
    index, space_keys = ptp.build_title_index(db_path)
    assert index == {}
    assert space_keys == {"100": "DOCS", "200": "ENG"}


def test_same_title_in_two_spaces_does_not_collide(db_path, add_page):
    add_page("1", "Overview", "", space_id="100")
    add_page("2", "Overview", "", space_id="200")
    index, _ = ptp.build_title_index(db_path)
    assert index == {("docs", "overview"): "1", ("eng", "overview"): "2"}


def test_pids_are_strings(db_path, add_page):
    add_page(1, "A", "")
    index, _ = ptp.build_title_index(db_path)
    assert all(isinstance(pid, str) for pid in index.values())


def test_integer_space_ids_in_config_still_match(db_path, add_page, monkeypatch):
    monkeypatch.setattr(space_utils, "list_configured_spaces", lambda: [{"id": 100, "key": "DOCS", "name": "Docs"}])
    add_page("1", "Home", "", space_id="100")
    index, space_keys = ptp.build_title_index(db_path)
    assert index == {("docs", "home"): "1"}
    assert space_keys == {"100": "DOCS"}


class TestNormalizedCollisions:
    """Confluence forbids exact duplicate titles per space, not case/whitespace variants."""

    def test_variants_collapse_to_one_entry(self, db_path, add_page):
        add_page("101", "FAQ", "")
        add_page("102", "faq ", "")
        index, _ = ptp.build_title_index(db_path)
        assert list(index) == [("docs", "faq")]
        assert index[("docs", "faq")] in {"101", "102"}

    def test_winner_is_stable_across_builds(self, db_path, add_page):
        add_page("101", "FAQ", "")
        add_page("102", "faq ", "")
        first, _ = ptp.build_title_index(db_path)
        second, _ = ptp.build_title_index(db_path)
        assert first == second

    @pytest.mark.xfail(
        reason="build_title_index has no ORDER BY, so the winner depends on row order. "
               "Add ORDER BY id to its query, then delete this marker.",
        strict=False,
    )
    def test_winner_is_independent_of_insert_order(self, make_db):
        winners = []
        for order in ([("101", "FAQ"), ("102", "faq ")], [("102", "faq "), ("101", "FAQ")]):
            path = make_db([{"id": pid, "title": title} for pid, title in order])
            index, _ = ptp.build_title_index(path)
            winners.append(index[("docs", "faq")])
        assert winners[0] == winners[1]