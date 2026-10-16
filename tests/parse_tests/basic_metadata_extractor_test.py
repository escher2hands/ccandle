# Tests for the basic-metadata step (eval notes, lead paragraph, bulk run).
# Threshold boundaries are derived from the eval_defs constants, so the tests check the
# comparison logic (> vs >=) at the edge for whatever values are configured.

import json
import math
import pytest
from bs4 import BeautifulSoup
from ccandle.config.config_app import APP_HANDLE
from ccandle.pages.parsing import basic_metadata_extractor as bm            # <- adjust if needed
from ccandle.pages.parsing import parse_to_plain_text as ptt
from ccandle.pages.parsing.eval_defs import *
from ccandle.pages.parsing.link_marker_defs import iter_markers, render_marker
from ccandle.pages.parsing.paragraph_parser import extract_lead_paragraph_from_soup

TOC = '<ac:structured-macro ac:name="toc"></ac:structured-macro>'

# A page long enough to trip every length-based note regardless of how thresholds are tuned.
LONG_PAGE = max(WORDS_PER_PAGE_MAX, 2 * WORDS_PER_HEADER_MAX, WORDS_UNTIL_TOC) + 1


def link(title, space=None, body=None):
    space_attr = f' ri:space-key="{space}"' if space else ""
    body_html = f"<ac:link-body>{body}</ac:link-body>" if body else ""
    return f'<ac:link><ri:page ri:content-title="{title}"{space_attr}/>{body_html}</ac:link>'


def headers(n):
    return "".join(f"<h2>Header {i}</h2>" for i in range(n))


def bullets(n):
    return "\n".join("- item" for _ in range(n))


def run_notes(html="", plain_text="", word_count=0, space_id="100", title_index=None, space_keys=None):
    """Call _get_eval_notes directly with synthetic word_count / plain_text."""
    soup = BeautifulSoup(html, "html.parser")
    lead_text, data = bm._get_eval_notes(
        html, soup, plain_text, space_id, word_count,
        title_index or {}, space_keys if space_keys is not None else {"100": "DOCS"},
    )
    return lead_text, json.loads(data["serialized_notes"])


def lead_html(filler_words, n_links):
    """A lone paragraph: `filler_words` plain words plus `n_links` one-word links."""
    filler = " ".join(["word"] * filler_words)
    links = " ".join(link(f"Page {i}", body="x") for i in range(n_links))
    return f"<p>{filler} {links}</p>"


# ---------------------------------------------------------------------------
# Eval notes: one block per note, each with a boundary pair
# ---------------------------------------------------------------------------

class TestPageTooLong:
    @pytest.mark.parametrize("words, flagged", [
        (WORDS_PER_PAGE_MAX, False),
        (WORDS_PER_PAGE_MAX + 1, True),
    ])
    def test_boundary(self, words, flagged):
        _, notes = run_notes(word_count=words)
        assert (NOTES_PAGE_TOO_LONG in notes) is flagged


class TestHeadersTooFew:
    @pytest.mark.parametrize("n_headers, words, flagged", [
        (1, WORDS_PER_HEADER_MAX, False),                 # exactly at the per-header limit
        (1, WORDS_PER_HEADER_MAX + 1, True),
        (0, 2 * WORDS_PER_HEADER_MAX, False),             # no headers: allowed up to 2x the limit
        (0, 2 * WORDS_PER_HEADER_MAX + 1, True),
        (0, 0, False),                                    # empty page must not divide by zero
        # long but well structured: just enough headers to stay at the limit.
        # (A bare `or word_count > 2x` clause would wrongly flag this.)
        (math.ceil(LONG_PAGE / WORDS_PER_HEADER_MAX), LONG_PAGE, False),
    ])
    def test_boundary(self, n_headers, words, flagged):
        _, notes = run_notes(html=headers(n_headers), word_count=words)
        assert (NOTES_HEADERS_TOO_FEW in notes) is flagged

    def test_just_over_the_per_header_limit_on_a_long_page(self):
        n = 6
        _, notes = run_notes(html=headers(n), word_count=n * (WORDS_PER_HEADER_MAX + 1))
        assert NOTES_HEADERS_TOO_FEW in notes


class TestTocMissing:
    @pytest.mark.parametrize("html, words, flagged", [
        ("", WORDS_UNTIL_TOC, False),
        ("", WORDS_UNTIL_TOC + 1, True),
        (TOC, WORDS_UNTIL_TOC + 1, False),
        (TOC, 5 * WORDS_UNTIL_TOC, False),
    ])
    def test_boundary(self, html, words, flagged):
        _, notes = run_notes(html=html, word_count=words)
        assert (NOTES_TOC_MISSING in notes) is flagged


class TestBulletsTooDense:
    # Many bullets, so word_count can sit exactly on the words-per-bullet limit.
    N = WORDS_UNTIL_TOC

    @pytest.mark.parametrize("words, n_bullets, flagged", [
        (WORDS_PER_BULLET_MIN * N, N, False),             # exactly at the limit: not below it
        (WORDS_PER_BULLET_MIN * N - 1, N, True),          # just under
        (WORDS_UNTIL_TOC + 1, 0, False),                  # zero bullets: must not raise, must not flag
        (WORDS_UNTIL_TOC + 1, 1, False),
        (WORDS_UNTIL_TOC, N, False),                      # at the TOC threshold the check is skipped
    ])
    def test_boundary(self, words, n_bullets, flagged):
        _, notes = run_notes(plain_text=bullets(n_bullets), word_count=words)
        assert (NOTES_BULLETS_TOO_DENSE in notes) is flagged

    def test_metric_is_whole_page_words_per_bullet(self):
        # Page words / bullet count, not bullet length: a page that is mostly prose
        # but has many bullets still reads as dense.
        words = WORDS_UNTIL_TOC + 200
        _, notes = run_notes(plain_text=bullets(words // 2), word_count=words)
        assert NOTES_BULLETS_TOO_DENSE in notes


class TestLeadParaGood:
    # n_links one-word links plus filler words; the lead's word count is their sum.
    LINKS = PARA_LINKS_MIN + 1
    FILLER_AT_LIMIT = PARA_LENGTH_MIN - LINKS             # total words == PARA_LENGTH_MIN

    @pytest.mark.parametrize("filler, n_links, flagged", [
        (FILLER_AT_LIMIT, LINKS, False),                  # exactly at the length limit
        (FILLER_AT_LIMIT + 1, LINKS, True),
        (PARA_LENGTH_MIN + 10, PARA_LINKS_MIN, False),    # exactly at the link limit
        (PARA_LENGTH_MIN + 10, PARA_LINKS_MIN + 1, True),
    ])
    def test_boundary(self, filler, n_links, flagged):
        _, notes = run_notes(html=lead_html(filler, n_links))
        assert (NOTES_LEAD_PARA_GOOD in notes) is flagged

    def test_page_without_lead_paragraph_stores_empty_string(self):
        lead_text, notes = run_notes(html="<h2>Only a heading</h2>")
        assert lead_text == ""
        assert NOTES_LEAD_PARA_GOOD not in notes

    def test_empty_html(self):
        lead_text, notes = run_notes(html="")
        assert lead_text == ""
        assert notes == []


class TestSerialization:
    def test_notes_are_a_json_list_in_stable_order(self):
        _, notes = run_notes(html="", plain_text=bullets(LONG_PAGE), word_count=LONG_PAGE)
        assert notes == [NOTES_PAGE_TOO_LONG, NOTES_HEADERS_TOO_FEW,
                         NOTES_TOC_MISSING, NOTES_BULLETS_TOO_DENSE]

    def test_no_notes_is_an_empty_json_list(self):
        soup = BeautifulSoup("", "html.parser")
        _, data = bm._get_eval_notes("", soup, "", "100", 0, {}, {"100": "DOCS"})
        assert data["serialized_notes"] == "[]"


# ---------------------------------------------------------------------------
# Lead paragraph extraction (paragraph_parser)
# ---------------------------------------------------------------------------

def lead_of(html):
    return extract_lead_paragraph_from_soup(BeautifulSoup(html, "html.parser"))


class TestLeadParagraphExtraction:
    def test_returns_html_string(self):
        result = lead_of("<p>This is a real lead paragraph</p>")
        assert isinstance(result, str)
        assert "real lead paragraph" in result

    def test_skips_leading_headings(self):
        result = lead_of("<h1>Title</h1><p>The actual lead paragraph</p>")
        assert "actual lead" in result
        assert "Title" not in result

    def test_paragraph_followed_by_list_includes_the_list(self):
        result = lead_of("<p>Intro to the list</p><ul><li>one</li></ul><p>Later text</p>")
        assert "Intro to the list" in result
        assert "<li>one</li>" in result
        assert "Later text" not in result

    def test_one_word_paragraph_is_skipped(self):
        result = lead_of("<p>Hi</p><p>This one is long enough</p>")
        assert "long enough" in result
        assert "Hi" not in result.replace("This", "")

    def test_short_paragraph_with_image_is_skipped(self):
        result = lead_of("<p><ac:image></ac:image>three short words</p><p>The real lead text goes here</p>")
        assert "real lead" in result
        assert "three short words" not in result

    def test_only_headings_and_toc_gives_none(self):
        assert lead_of(f"<h1>Title</h1>{TOC}<h2>Section</h2>") is None

    def test_first_layout_cell_with_a_lead_wins(self):
        html = ("<ac:layout><ac:layout-section>"
                "<ac:layout-cell><h2>Only heading here</h2></ac:layout-cell>"
                "<ac:layout-cell><p>Lead from the second cell</p></ac:layout-cell>"
                "<ac:layout-cell><p>Lead from the third cell</p></ac:layout-cell>"
                "</ac:layout-section></ac:layout>")
        result = lead_of(html)
        assert "second cell" in result
        assert "third cell" not in result

    def test_adf_fallback_paragraph_is_ignored(self):
        html = "<ac:adf-fallback><p>Duplicated macro content</p></ac:adf-fallback>"
        assert lead_of(html) is None


# ---------------------------------------------------------------------------
# Bulk run (DB round trip)
# ---------------------------------------------------------------------------

def parse_then_metadata(db_path, pids=None):
    ptt.extract_plain_texts_in_bulk(quiet=True, path_to_db=db_path)
    bm.add_basic_metadata_in_bulk(pids=pids, path_to_db=db_path, quiet=True)


class TestBulk:
    def _seed(self, add_page):
        add_page(101, title="Target Page", space_id="100", html="<p>I am the target page</p>")
        add_page(1, title="Source", space_id="100",
                 html=f"<h2>Intro</h2><p>Some words here {link('Target Page')}</p><img/>")
        add_page(2, title="Other", space_id="200", html="<p>Plain page here</p>")

    def test_writes_every_metadata_column(self, db_path, add_page, read_row):
        self._seed(add_page)
        parse_then_metadata(db_path)
        row = read_row(1)
        assert row["link_count"] == 1
        assert row["image_count"] is not None
        assert row["lead_para"]
        assert row["has_link_tree"] is not None
        assert json.loads(row["eval_notes"]) == []

    def test_empty_page_gets_zero_counts_and_empty_lead(self, db_path, add_page, read_row):
        add_page(5, title="Blank", space_id="100", html="", plain_text="", word_count=0)
        bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)
        row = read_row(5)
        assert row["link_count"] == 0
        assert row["image_count"] == 0
        assert row["lead_para"] == ""
        assert row["eval_notes"] == "[]"

    def test_page_without_lead_stores_empty_string_not_null(self, db_path, add_page, read_row):
        add_page(6, title="Headings", space_id="100", html="<h2>Only a heading</h2>")
        parse_then_metadata(db_path)
        assert read_row(6)["lead_para"] == ""

    def test_idempotent(self, db_path, add_page, read_all_rows):
        self._seed(add_page)
        parse_then_metadata(db_path)
        first = read_all_rows()
        bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)
        assert read_all_rows() == first

    def test_subset_run_leaves_other_pages_untouched(self, db_path, add_page, read_row):
        self._seed(add_page)
        ptt.extract_plain_texts_in_bulk(quiet=True, path_to_db=db_path)
        bm.add_basic_metadata_in_bulk(pids=["1"], path_to_db=db_path, quiet=True)
        assert read_row(1)["eval_notes"] is not None
        assert read_row(2)["eval_notes"] is None
        assert read_row(101)["eval_notes"] is None

    @pytest.mark.parametrize("pids", [None, []])
    def test_none_or_empty_list_processes_every_page(self, db_path, add_page, read_all_rows, pids):
        # Intended UX: no subset given means the whole corpus.
        self._seed(add_page)
        parse_then_metadata(db_path, pids=pids)
        assert all(row["eval_notes"] is not None for row in read_all_rows().values())

    def test_page_in_unconfigured_space_does_not_raise(self, db_path, add_page, read_row):
        add_page(101, title="Target Page", space_id="100")
        add_page(9, title="Orphan", space_id="999",
                 html=f"<p>Some words here {link('Target Page')}</p>")
        parse_then_metadata(db_path)
        lead = read_row(9)["lead_para"]
        assert lead
        assert render_marker("DOCS", "101", resolved=True) not in lead


class TestUnparsedPagesExit:
    def test_exits_with_code_1_and_points_to_parse_text(self, db_path, add_page, capsys):
        add_page(1, title="Parsed", html="<p>ok text</p>", plain_text="ok text", word_count=2)
        add_page(2, title="Unparsed", html="<p>never parsed</p>")  # NULL plain_text / word_count
        with pytest.raises(SystemExit) as exc:
            bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)
        assert exc.value.code == 1
        out = capsys.readouterr().out
        assert "parse_text" in out
        assert APP_HANDLE in out

    def test_nothing_is_written_when_it_exits(self, db_path, add_page, read_row):
        add_page(1, title="Parsed", html="<p>ok text</p>", plain_text="ok text", word_count=2)
        add_page(2, title="Unparsed", html="<p>never parsed</p>")
        with pytest.raises(SystemExit):
            bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)
        for pid in (1, 2):
            row = read_row(pid)
            assert row["eval_notes"] is None
            assert row["lead_para"] is None

    def test_empty_string_and_zero_count_is_parsed_not_missing(self, db_path, add_page):
        add_page(1, title="Blank", html="", plain_text="", word_count=0)
        bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)  # must not exit

    @pytest.mark.parametrize("plain_text, word_count", [(None, 5), ("text", None)])
    def test_either_column_null_counts_as_unparsed(self, db_path, add_page, plain_text, word_count):
        add_page(1, title="Half", html="<p>x</p>", plain_text=plain_text, word_count=word_count)
        with pytest.raises(SystemExit):
            bm.add_basic_metadata_in_bulk(path_to_db=db_path, quiet=True)


# ---------------------------------------------------------------------------
# Cross-module invariant: lead_para links are consistent with plain_text links
# ---------------------------------------------------------------------------

class TestLeadParaMatchesPlainText:
    """The regression test for the original bug: lead_para rendered every link as a
    ulink while plain_text resolved the same links to page ids."""

    def _build(self, add_page):
        add_page(101, title="Target Page", space_id="100")
        add_page(202, title="Other Page", space_id="200")
        words = " ".join(["word"] * 25)
        add_page(1, title="Source", space_id="100", html=(
            f"<h2>Intro</h2>"
            f"<p>{words} {link('Target Page')} {link('Missing One')} "
            f"{link('Other Page', space='ENG')} {link('Missing Two')}</p>"
            f"<p>Later body paragraph</p>"
        ))

    def test_lead_markers_are_a_prefix_of_plain_text_markers(self, db_path, add_page, read_row):
        self._build(add_page)
        parse_then_metadata(db_path)
        row = read_row(1)
        lead = [m.entry for m in iter_markers(row["lead_para"])]
        full = [m.entry for m in iter_markers(row["plain_text"])]
        assert len(lead) == 4
        assert set(lead) <= set(full)
        assert lead == full[:len(lead)]

    def test_resolution_is_identical_in_both_columns(self, db_path, add_page, read_row):
        self._build(add_page)
        parse_then_metadata(db_path)
        row = read_row(1)
        for marker in (
            render_marker("DOCS", "101", resolved=True),
            render_marker("ENG", "202", resolved=True),
            render_marker("DOCS", "Missing One", resolved=False),
        ):
            assert marker in row["lead_para"]
            assert marker in row["plain_text"]

    def test_good_lead_paragraph_is_flagged(self, db_path, add_page, read_row):
        self._build(add_page)
        parse_then_metadata(db_path)
        assert NOTES_LEAD_PARA_GOOD in json.loads(read_row(1)["eval_notes"])