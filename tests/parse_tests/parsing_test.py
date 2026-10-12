import pytest

from ccandle.pages.parsing import parse_to_plain_text as ptp
from ccandle.pages.parsing.link_marker_defs import Marker, iter_markers

# Title index shape: {(casefolded space key, casefolded title): pid}
INDEX = {
    ("docs", "getting started"): "111",
    ("docs", "faq: billing"): "333",
    ("docs", "q&a"): "444",
    ("eng", "design doc"): "222",
}


def link(title, space=None, body=None, plain_body=None):
    """Builds a storage-format ac:link. `title` is written into the attribute as-is (pre-escaped)."""
    space_attr = f' ri:space-key="{space}"' if space else ""
    inner = f'<ri:page ri:content-title="{title}"{space_attr} />'
    if body is not None:
        inner += f"<ac:link-body>{body}</ac:link-body>"
    if plain_body is not None:
        inner += f"<ac:plain-text-link-body><![CDATA[{plain_body}]]></ac:plain-text-link-body>"
    return f"<ac:link>{inner}</ac:link>"


def extract(html, space="DOCS", index=INDEX):
    return ptp.extract_text_and_word_count_from_html(html, space_key=space, title_index=index)


def text_of(html, **kwargs):
    return extract(html, **kwargs)[0]


def markers_of(html, **kwargs):
    return list(iter_markers(text_of(html, **kwargs)))


# ---------------------------------------------------------------------------
# Block structure
# ---------------------------------------------------------------------------

class TestBlocks:
    @pytest.mark.parametrize("html", [None, "", "   ", "<p>   </p>", "<p></p>"])
    def test_empty_inputs(self, html):
        assert extract(html) == ("", 0)

    def test_h1_h2_get_heading_markers_others_do_not(self):
        html = "<h1>Intro</h1><h2>Sub</h2><h3>Minor</h3><p>Body</p>"
        assert extract(html) == ("[[Heading: Intro]]\n[[Heading: Sub]]\nMinor\nBody", 4)

    def test_list_items_get_dash_prefix(self):
        assert extract("<ul><li>one</li><li>two</li></ul>") == ("- one\n- two", 2)

    def test_table_becomes_one_line_with_cells_separated(self):
        html = "<table><tbody><tr><td>a</td><td>b</td></tr><tr><td>c</td><td>d</td></tr></tbody></table>"
        assert extract(html) == ("a b c d", 4)

    def test_blocks_come_out_in_document_order(self):
        assert text_of("<p>first</p><ul><li>second</li></ul><p>third</p>") == "first\n- second\nthird"

    # --- characterization: these pin current behavior, change them deliberately ---

    def test_nested_list_is_flattened_into_parent_item(self):
        assert extract("<ul><li>top<ul><li>child</li></ul></li></ul>") == ("- top child", 2)

    def test_repeated_blocks_are_deduplicated(self):
        assert extract("<p>Yes</p><p>No</p><p>Yes</p>") == ("Yes\nNo", 2)


# ---------------------------------------------------------------------------
# Whitespace and inline joining
# ---------------------------------------------------------------------------

class TestInlineJoining:
    def test_punctuation_after_inline_tag_stays_attached(self):
        assert extract("<p>a <strong>bold</strong>, c</p>") == ("a bold, c", 3)

    def test_mid_word_formatting_is_one_word(self):
        assert extract("<p>co-<em>operate</em></p>") == ("co-operate", 1)

    def test_br_separates_words(self):
        assert text_of("<p>line<br/>break</p>") == "line break"

    def test_empty_inline_tag_vanishes_without_adding_space(self):
        assert text_of("<p>foo<span></span>bar</p>") == "foobar"

    def test_whitespace_only_inline_tag_keeps_a_space(self):
        assert text_of("<p>foo<span> </span>bar</p>") == "foo bar"

    def test_runs_of_whitespace_collapse(self):
        assert text_of("<p>a  \n   b\t\tc</p>") == "a b c"

    def test_pre_newlines_collapse_to_one_line(self):
        assert text_of("<pre>line1\nline2</pre>") == "line1 line2"


# ---------------------------------------------------------------------------
# Excerpts, macros, fallbacks
# ---------------------------------------------------------------------------

EXCERPT = (
    '<ac:structured-macro ac:name="excerpt-include">'
    '<ri:page ri:content-title="Source Page" /></ac:structured-macro>'
)


class TestMacros:
    def test_excerpt_include_becomes_placeholder(self):
        assert text_of(EXCERPT) == "[[Excerpt from: Source Page]]"

    def test_excerpt_include_without_page_reference(self):
        html = '<ac:structured-macro ac:name="excerpt-include"></ac:structured-macro>'
        assert text_of(html) == "[[Excerpt from: Unknown page]]"

    def test_other_macro_bodies_are_kept(self):
        html = (
            '<ac:structured-macro ac:name="info"><ac:rich-text-body>'
            "<p>Heads up</p></ac:rich-text-body></ac:structured-macro>"
        )
        assert extract(html) == ("Heads up", 2)

    def test_adf_fallback_content_is_dropped(self):
        html = "<p>real</p><ac:adf-fallback><p>duplicate</p></ac:adf-fallback>"
        assert extract(html) == ("real", 1)

    @pytest.mark.xfail(strict=True, reason="placeholder words ([[Excerpt from: ...]]) are counted as page words")
    def test_excerpt_placeholder_adds_no_words(self):
        assert extract(EXCERPT)[1] == 0


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------

class TestLinkResolution:
    def test_bare_link_resolves_and_shows_title(self):
        html = f"<p>See {link('Getting Started')}.</p>"
        assert text_of(html) == "See Getting Started [[link to: DOCS:111]]."

    def test_link_body_is_the_visible_text(self):
        html = f"<p>See {link('Getting Started', body='the guide')} now.</p>"
        assert text_of(html) == "See the guide [[link to: DOCS:111]] now."

    def test_plain_text_link_body_is_the_visible_text(self):
        html = f"<p>See {link('Getting Started', plain_body='the guide')} now.</p>"
        assert text_of(html) == "See the guide [[link to: DOCS:111]] now."

    def test_target_not_in_corpus_becomes_ulink_with_title(self):
        assert text_of(f"<p>{link('Missing Page')}</p>") == "Missing Page [[ulink to: DOCS:Missing Page]]"

    def test_explicit_space_key_resolves_cross_space(self):
        assert text_of(f"<p>{link('Design Doc', space='ENG')}</p>") == "Design Doc [[link to: ENG:222]]"

    def test_explicit_space_key_works_even_if_page_space_unknown(self):
        assert markers_of(f"<p>{link('Design Doc', space='ENG')}</p>", space=None) == [Marker("link", "ENG", "222")]

    def test_same_title_in_two_spaces_is_not_confused(self):
        index = {("docs", "overview"): "1", ("eng", "overview"): "2"}
        assert markers_of(f"<p>{link('Overview')}</p>", index=index)[0].target == "1"
        assert markers_of(f"<p>{link('Overview', space='ENG')}</p>", index=index)[0].target == "2"

    def test_no_space_key_means_the_linking_pages_own_space(self):
        assert markers_of(f"<p>{link('Design Doc')}</p>", space="ENG") == [Marker("link", "ENG", "222")]
        assert markers_of(f"<p>{link('Design Doc')}</p>", space="DOCS")[0].resolved is False

    @pytest.mark.parametrize("title", ["getting started", "GETTING   STARTED", "Getting  Started "])
    def test_title_match_ignores_case_and_whitespace(self, title):
        assert markers_of(f"<p>{link(title)}</p>") == [Marker("link", "DOCS", "111")]

    def test_space_key_match_ignores_case(self):
        assert markers_of(f"<p>{link('Design Doc', space='eng')}</p>")[0].resolved is True

    def test_html_entities_in_title_are_decoded_before_lookup(self):
        html = f"<p>{link('Q&amp;A')}</p>"
        assert text_of(html) == "Q&A [[link to: DOCS:444]]"

    def test_title_containing_colon_resolves(self):
        assert markers_of(f"<p>{link('FAQ: Billing')}</p>") == [Marker("link", "DOCS", "333")]

    def test_unresolved_title_containing_colon_survives_round_trip(self):
        assert markers_of(f"<p>{link('Unknown: Thing')}</p>") == [Marker("ulink", "DOCS", "Unknown: Thing")]

    def test_unresolved_title_containing_brackets_survives_round_trip(self):
        assert markers_of(f"<p>{link('Foo [bar]')}</p>") == [Marker("ulink", "DOCS", "Foo [bar]")]

    def test_unknown_page_space_gives_placeholder_key(self):
        html = f"<p>{link('Getting Started')}</p>"
        assert markers_of(html, space=None) == [Marker("ulink", "?", "Getting Started")]

    def test_empty_title_index_means_everything_is_unresolved(self):
        assert [m.resolved for m in iter_markers(text_of(f"<p>{link('Getting Started')}</p>", index={}))] == [False]

    def test_title_index_none_is_allowed(self):
        assert ptp.extract_text_and_word_count_from_html(
            f"<p>{link('Getting Started')}</p>", space_key="DOCS"
        )[0].endswith("[[ulink to: DOCS:Getting Started]]")

    def test_multiple_links_come_out_in_order(self):
        html = f"<p>{link('Getting Started')} then {link('Missing')} then {link('Design Doc', space='ENG')}</p>"
        assert [m.entry for m in iter_markers(text_of(html))] == ["DOCS:111", "DOCS:Missing", "ENG:222"]

    def test_adjacent_links_both_get_markers(self):
        html = f"<p>{link('Getting Started')}{link('Design Doc', space='ENG')}</p>"
        assert [m.entry for m in iter_markers(text_of(html))] == ["DOCS:111", "ENG:222"]

    def test_link_in_adf_fallback_is_not_counted(self):
        html = f"<p>x</p><ac:adf-fallback><p>{link('Getting Started')}</p></ac:adf-fallback>"
        assert markers_of(html) == []

    def test_link_inside_heading_is_marked_and_not_counted_as_words(self):
        html = f"<h1>See {link('Getting Started', body='guide')}</h1>"
        text, words = extract(html)
        assert text == "[[Heading: See guide [[link to: DOCS:111]]]]"
        assert words == 2
        assert [m.entry for m in iter_markers(text)] == ["DOCS:111"]

    def test_bare_link_title_can_be_hidden(self, monkeypatch):
        monkeypatch.setattr(ptp, "BARE_LINK_SHOWS_TITLE", False)
        assert text_of(f"<p>See {link('Getting Started')}.</p>") == "See [[link to: DOCS:111]]."

    def test_hidden_link_with_blank_body_keeps_marker_but_adds_no_words(self):
        html = f"<p>Intro{link('Getting Started', plain_body=' ')}</p>"
        text, words = extract(html)
        assert [m.entry for m in iter_markers(text)] == ["DOCS:111"]
        assert words == 1

    # --- links that are not page links are left alone ---

    def test_user_mention_produces_no_marker(self):
        html = '<p>Hi <ac:link><ri:user ri:account-id="abc" /></ac:link></p>'
        assert extract(html) == ("Hi", 1)

    def test_in_page_anchor_link_keeps_its_text_and_has_no_marker(self):
        html = '<p>Go <ac:link ac:anchor="sec"><ac:link-body>up</ac:link-body></ac:link></p>'
        assert extract(html) == ("Go up", 2)

    def test_attachment_link_produces_no_marker(self):
        html = '<p><ac:link><ri:attachment ri:filename="a.pdf" /></ac:link>text</p>'
        assert markers_of(html) == []


class TestPunctuationAroundMarkers:
    @pytest.mark.parametrize("html, expected", [
        (f"<p>keep it updated {link('Getting Started')}: with all", "keep it updated Getting Started [[link to: DOCS:111]]: with all"),
        (f"<p>(see {link('Getting Started')}) and more", "(see Getting Started [[link to: DOCS:111]]) and more"),
        (f"<p>{link('Getting Started')}, or {link('Missing')}.", "Getting Started [[link to: DOCS:111]], or Missing [[ulink to: DOCS:Missing]]."),
    ])
    def test_punctuation_stays_glued_to_the_marker(self, html, expected):
        assert text_of(html + "</p>") == expected


# ---------------------------------------------------------------------------
# Word counts
# ---------------------------------------------------------------------------

class TestWordCount:
    def test_markers_are_not_words(self):
        html = f"<p>See {link('Getting Started', body='guide')} here</p>"
        assert extract(html)[1] == 3

    def test_bare_link_title_counts_as_words(self):
        assert extract(f"<p>See {link('Getting Started')} here</p>")[1] == 4

    def test_heading_markup_is_not_counted(self):
        assert extract("<h1>Two words</h1>")[1] == 2

    def test_deduplicated_blocks_are_counted_once(self):
        assert extract("<p>same text</p><p>same text</p>")[1] == 2

    @pytest.mark.xfail(strict=True, reason="punctuation glued to a marker is left behind as a standalone 'word'")
    def test_punctuation_after_a_marker_is_not_a_word(self):
        assert extract(f"<p>See {link('Getting Started', body='guide')}.</p>")[1] == 2


# ---------------------------------------------------------------------------
# Regression: real-world shape (title with colon, hidden blank-body link, repeat in next paragraph)
# ---------------------------------------------------------------------------

def test_real_world_account_types_page():
    html = (
        "<p>View here for a non-technical introduction to the topic: "
        '<ac:link><ri:page ri:content-title="Account Types and Selection: Sold-To vs. Tenants" /></ac:link>'
        '<ac:link><ri:page ri:content-title="Customer Account Hierarchy" />'
        "<ac:plain-text-link-body><![CDATA[ ]]></ac:plain-text-link-body></ac:link></p>"
        '<p><ac:link><ri:page ri:content-title="Customer Account Hierarchy" /></ac:link></p>'
    )
    index = {
        ("a3sa", "account types and selection: sold-to vs. tenants"): "601560807",
        ("a3sa", "customer account hierarchy"): "601563268",
    }
    text, words = extract(html, space="A3SA", index=index)
    assert text == (
        "View here for a non-technical introduction to the topic: "
        "Account Types and Selection: Sold-To vs. Tenants [[link to: A3SA:601560807]]"
        "[[link to: A3SA:601563268]]\n"
        "Customer Account Hierarchy [[link to: A3SA:601563268]]"
    )
    assert words == 19


def test_same_input_gives_identical_output_every_time():
    html = f"<h1>T</h1><p>See {link('Getting Started')} and {link('Missing')}</p><ul><li>x</li></ul>"
    assert len({extract(html) for _ in range(5)}) == 1


# ---------------------------------------------------------------------------
# build_title_index
# ---------------------------------------------------------------------------

class TestBuildTitleIndex:
    def test_index_is_normalized_and_skips_unindexable_pages(self, db_path, add_page):
        add_page("1", "Getting  Started", "<p>x</p>", space_id="100")
        add_page("2", "Design Doc", "<p>x</p>", space_id="200")
        add_page("3", "Hidden", "<p>x</p>", space_id="999")   # space not configured
        add_page("4", None, "<p>x</p>", space_id="100")        # no title
        index = ptp.build_title_index(db_path, {"100": "DOCS", "200": "ENG"})
        assert index == {("docs", "getting started"): "1", ("eng", "design doc"): "2"}


# ---------------------------------------------------------------------------
# Bulk flow against a real (temporary) SQLite DB
# ---------------------------------------------------------------------------

def run(db_path, pid_list=None):
    return ptp.extract_plain_texts_in_bulk(pid_list, quiet=True, path_to_db=db_path)


class TestBulk:
    def test_writes_text_word_count_and_links_list(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "Home", f"<h1>Home</h1><p>See {link('Other')} and {link('Gone')}</p>")
        add_page("2", "Other", "<p>Other body</p>")
        run(db_path)
        assert read_page("1") == {
            "text": "[[Heading: Home]]\nSee Other [[link to: DOCS:2]] and Gone [[ulink to: DOCS:Gone]]",
            "word_count": 5,
            "links": ["DOCS:2", "DOCS:Gone"],
        }

    def test_returns_one_record_per_processed_page(self, db_path, add_page, configured_spaces):
        add_page("1", "A", "<p>one</p>")
        add_page("2", "B", "<p>two words</p>")
        records = run(db_path)
        assert {r["id"]: (r["text"], r["word_count"]) for r in records} == {"1": ("one", 1), "2": ("two words", 2)}
        assert all(isinstance(r["id"], str) for r in records)

    def test_none_means_all_pages(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "A", "<p>one</p>")
        add_page("2", "B", "<p>two</p>")
        run(db_path, None)
        assert read_page("1")["text"] == "one" and read_page("2")["text"] == "two"

    def test_subset_only_touches_listed_pages(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "A", "<p>one</p>")
        add_page("2", "B", "<p>two</p>")
        run(db_path, ["1"])
        assert read_page("1")["text"] == "one"
        assert read_page("2") == {"text": None, "word_count": None, "links": None}

    def test_int_and_str_pids_are_both_accepted(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "A", "<p>one</p>")
        add_page("2", "B", "<p>two</p>")
        run(db_path, [1, "2"])
        assert read_page("1")["text"] == "one" and read_page("2")["text"] == "two"

    @pytest.mark.parametrize("html", [None, ""])
    def test_page_without_html_gets_empty_values(self, db_path, add_page, read_page, configured_spaces, html):
        add_page("1", "A", html)
        run(db_path)
        assert read_page("1") == {"text": "", "word_count": 0, "links": []}

    def test_links_resolve_across_configured_spaces(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "Home", f"<p>{link('Design Doc', space='ENG')}</p>", space_id="100")
        add_page("2", "Design Doc", "<p>x</p>", space_id="200")
        run(db_path)
        assert read_page("1")["links"] == ["ENG:2"]

    def test_pages_in_unconfigured_spaces_are_not_link_targets_and_have_unknown_key(
        self, db_path, add_page, read_page, configured_spaces
    ):
        add_page("1", "Home", f"<p>{link('Hidden')}</p>", space_id="100")
        add_page("9", "Hidden", f"<p>{link('Home')}</p>", space_id="999")
        run(db_path)
        assert read_page("1")["links"] == ["DOCS:Hidden"]
        assert read_page("9")["links"] == ["?:Home"]

    def test_integer_space_ids_in_config_still_match(self, db_path, add_page, read_page, monkeypatch):
        monkeypatch.setattr(ptp, "list_configured_spaces", lambda: [{"id": 100, "key": "DOCS", "name": "Docs"}])
        add_page("1", "Home", f"<p>{link('Other')}</p>", space_id="100")
        add_page("2", "Other", "<p>x</p>", space_id="100")
        run(db_path)
        assert read_page("1")["links"] == ["DOCS:2"]

    def test_rerun_is_idempotent(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "Home", f"<p>See {link('Other')} and {link('Gone')}</p>")
        add_page("2", "Other", "<p>body</p>")
        run(db_path)
        first = (read_page("1"), read_page("2"))
        run(db_path)
        assert (read_page("1"), read_page("2")) == first

    def test_reparsing_a_subset_matches_a_full_run(self, db_path, add_page, read_page, configured_spaces):
        """The point of the single pass: parsing one page alone must give the same result as a full sync."""
        add_page("1", "Home", f"<p>See {link('Other')} and {link('Gone')}</p>")
        add_page("2", "Other", f"<p>{link('Home')}</p>")
        run(db_path)
        full = (read_page("1"), read_page("2"))
        run(db_path, ["1"])
        assert (read_page("1"), read_page("2")) == full

    def test_link_to_a_later_added_page_resolves_after_reparse(self, db_path, add_page, read_page, configured_spaces):
        add_page("1", "Home", f"<p>{link('Later')}</p>")
        run(db_path)
        assert read_page("1")["links"] == ["DOCS:Later"]
        add_page("2", "Later", "<p>x</p>")
        run(db_path, ["1"])
        assert read_page("1")["links"] == ["DOCS:2"]