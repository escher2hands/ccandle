"""
Tests for scrape_page_contents_from_server (second step of the sync pipeline).

Boundaries mocked: request_page_contents (network) and _store_page_contents
(DB write). _chunked is NOT mocked -- it's real internal logic (how pid_list
gets split into batches) and is exactly the kind of thing worth testing for
real rather than stubbing away.

We deliberately do NOT validate HTML structure/consistency here (bullets,
tables, macros, etc.) -- per project convention, Confluence's own storage
guarantees mean we trust page HTML is well-formed. That validation belongs
to the later plain-text/feature-extraction step, which needs much more
specific assertions. Here we only care that:
  1. fields get transformed/typed correctly (id, version as int, title,
     last_modified, html) with the HTML passed through byte-for-byte, and
  2. pages get processed and stored in chunks of chunk_size, incrementally,
     not gathered into a single end-of-run store call.

As with the metadata-scrape tests, fixture data lives in ONE place
(CONTENT_DEFS) so raw API payloads and expected-output assertions can't
drift apart from each other.
"""

import copy
import dataclasses

import pytest

from ccandle.pages.scrape_page_htmls import scrape_page_contents_from_server

MODULE = "ccandle.pages.scrape_page_htmls"  # adjust to your actual module path


# ---------------------------------------------------------------------------
# Single source of truth for fixture pages
# ---------------------------------------------------------------------------
#
# The four HTML bodies below are the ones supplied for this step: two
# "stub" style pages (simple bullet list + a report table) and two more
# "realistic" pages (headers, macros, layouts, nested links/images). They
# double as a starting corpus for the later feature-extraction tests --
# no need to invent new sample HTML there, just import CONTENT_DEFS.

STUB_HTML_1 = """
<p><br /></p><ul><li>Build version: 1.66.18</li><li>Environment: Patch</li></ul><p class="auto-cursor-target">Automated Regression execution report:</p><table class="wrapped"><colgroup><col style="width: 93.0px;" /><col style="width: 275.0px;" /></colgroup><tbody><tr><th>Area</th><th>Test Result</th></tr><tr><td>Regression</td><td><div class="content-wrapper"><p><ac:link><ri:attachment ri:filename="patch1.3_ios_report.html" /></ac:link></p></div></td></tr></tbody></table><p class="auto-cursor-target"><br /></p><p class="auto-cursor-target"><br /></p><p><br /></p>
"""

STUB_HTML_2 = """
<p><br /></p><ul><li>Build version: 1.65.14</li><li>Environment: Patch</li></ul><p class="auto-cursor-target">Automated regression execution report:</p><table class="wrapped"><colgroup><col style="width: 93.0px;" /><col style="width: 159.0px;" /></colgroup><tbody><tr><th>Area</th><th>Test Result</th></tr><tr><td colspan="1">Sanity</td><td colspan="1"><div class="content-wrapper"><p><ac:link><ri:attachment ri:filename="sanity.html" /></ac:link></p></div></td></tr><tr><td>Regression</td><td><div class="content-wrapper"><p><ac:link><ri:attachment ri:filename="latest_report_23July.html" /></ac:link></p></div></td></tr></tbody></table><p class="auto-cursor-target"><br /></p><p class="auto-cursor-target"><br /></p><p class="auto-cursor-target"><br /></p><p><br /></p><p><br /></p><p><br /></p><p><br /></p>
"""

REALISTIC_HTML_NAVBOX = """
<ac:image ac:align="center" ac:layout="center" ac:original-height="181" ac:original-width="446" ac:custom-width="true" ac:local-id="b01134ea280c" ac:alt="image-20260304-185301.png" ac:width="752"><ri:attachment ri:filename="image-20260304-185301.png" ri:version-at-save="1" /><ac:caption ac:local-id="cf1f84ed6a46"><p>(Navboxes are a way Wikipedia guides its readers through topics, surfacing pages which otherwise might be hidden)</p></ac:caption></ac:image><p local-id="88a4681b6807">Navboxes are a page element to improve self-navigability for users. They are a concept <a href="https://en.wikipedia.org/wiki/Wikipedia:Navigation_template">borrowed from Wikipedia</a>. They are one of a number of measures we take to <ac:link><ri:page ri:content-title="Information architecture / strategies for navigability" ri:version-at-save="2" /><ac:link-body>improve the findability</ac:link-body></ac:link> of information in our Confluence spaces, and one pillar of the <ac:link><ri:page ri:content-title="00 - Documentation philosophy and knowledge management principles" ri:version-at-save="6" /><ac:link-body>various quality themes in Confluence</ac:link-body></ac:link> overall.</p><h2 local-id="f8019318e36e">Creating navboxes</h2><p local-id="05ab1f050f40">The closest approximation we can achieve to Wikipedia style navboxes in Confluence is through:</p><ol start="1" local-id="7a3145586bc7"><li local-id="ae901158500a"><p local-id="a92f6c087eac">Labelling pages by topic</p></li><li local-id="2782e13725df"><p local-id="0d68fab9fdfb">Creating an excerpt macro in a given page on the topic, including &lsquo;navbox&rsquo; in the <em><span style="color: rgb(101,84,192);">name </span></em>of the macro</p></li><li local-id="e6cbbe48380a"><p local-id="fee5f3010763">Inserting a label filter macro <em><span style="color: rgb(101,84,192);">inside </span></em>the excerpt, configuring the topic label</p></li><li local-id="597cb4eb3c5a"><p local-id="636519be2ddb">adding an excerpt-include to the pages sharing the same label</p></li></ol><p local-id="103850ce5e2d">Note that it can be nice to include a description and a horizontal bar for visual separation from the page content.</p><p local-id="3c662756c01b">This page has a navbox as well! Try to edit this page to find how the macros relate.</p><p local-id="397259152518">
<ac:structured-macro ac:name="excerpt-include" ac:schema-version="1" ac:local-id="0851fca9-2d05-4746-9649-8fe80b6c36e8" ac:macro-id="c8d38983-94be-4615-bb89-0fdb93882cb9"><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="Elements of 'beautiful,' effective pages" ri:version-at-save="10" /></ac:link></ac:parameter><ac:parameter ac:name="name">page best practices navbox</ac:parameter><ac:parameter ac:name="nopanel">true</ac:parameter></ac:structured-macro>
</p><p /><p />
"""

REALISTIC_HTML_LANDING_PAGE = """
<ac:layout><ac:layout-section ac:type="fixed-width" ac:breakout-mode="default"><ac:layout-cell><ac:image ac:align="center" ac:layout="center" ac:original-height="711" ac:original-width="1424" ac:custom-width="true" ac:local-id="a1bc63966d1b" ac:alt="image-20260630-084524.png" ac:width="760"><ri:attachment ri:filename="image-20260630-084524.png" ri:version-at-save="1" /><ac:caption ac:local-id="0ad97377cec4"><p><em><span style="color: rgb(151,160,175);">(trail markers keep hikers from getting lost, like landing pages help readers from getting lost in our forest of documentation pages)</span></em></p></ac:caption></ac:image><p local-id="230b0a81cd86">Landing pages are a page type to provide <ac:link><ri:page ri:content-title="Information architecture / strategies for navigability" ri:version-at-save="2" /><ac:link-body><em>structure</em></ac:link-body></ac:link> and assist in navigation, rather than provide new <em>content</em>. Together with <ac:link><ri:page ri:content-title="Information architecture / strategies for navigability" ri:version-at-save="2" /><ac:link-body>other structures</ac:link-body></ac:link>, they can reduce reader&rsquo;s needs to rely on search alone, or excessive bookmarking of pages they fear they&rsquo;ll never find again.</p><h2 local-id="a152f49240a9">Example landing pages:</h2></ac:layout-cell></ac:layout-section><ac:layout-section ac:type="three_equal" ac:breakout-mode="wide" ac:breakout-width="1444" ac:local-id="188b7cde3efa"><ac:layout-cell ac:local-id="ce113943e296"><ac:link><ri:space ri:space-key="OPKB" /><ac:link-body><ac:image ac:align="center" ac:layout="center" ac:original-height="1584" ac:original-width="1171" ac:custom-width="true" ac:local-id="d92d92f3cc5e" ac:alt="image-20260630-124032.png" ac:width="449"><ri:attachment ri:filename="image-20260630-124032.png" ri:version-at-save="1" /></ac:image></ac:link-body></ac:link><p local-id="d8c119aabf0e" /></ac:layout-cell><ac:layout-cell ac:local-id="f5da95c2a974"><ac:link><ri:space ri:space-key="A3SA" /><ac:link-body><ac:image ac:align="center" ac:layout="center" ac:original-height="967" ac:original-width="694" ac:custom-width="true" ac:local-id="7049fff8864e" ac:alt="image-20260630-123909.png" ac:width="449"><ri:attachment ri:filename="image-20260630-123909.png" ri:version-at-save="1" /></ac:image></ac:link-body></ac:link><p local-id="d4e9ad50f9a9" /></ac:layout-cell><ac:layout-cell ac:local-id="76386a02baba"><ac:link><ri:page ri:space-key="A3SA" ri:content-title="00 - Getting Started in the ON!Track 3 Technical Wiki" ri:version-at-save="20" /><ac:link-body><ac:image ac:align="center" ac:layout="center" ac:original-height="969" ac:original-width="691" ac:custom-width="true" ac:local-id="732dea108224" ac:alt="image-20260630-123931.png" ac:width="449"><ri:attachment ri:filename="image-20260630-123931.png" ri:version-at-save="1" /></ac:image></ac:link-body></ac:link><p local-id="6889c33f8797" /></ac:layout-cell></ac:layout-section><ac:layout-section ac:type="fixed-width" ac:breakout-mode="default"><ac:layout-cell><h2 local-id="325742da3ba9">Key features:</h2><p local-id="dd64dc5df02f">Landing pages are a simple concept. Users 'land' on the page, and find:</p><ul local-id="c8f56d1f8d70"><li local-id="1cd63f0aa4d4"><p local-id="a5ba6bd38abf">a series of links to other pages (5, 10, 30 links)</p></li><li local-id="3b7ab0daf66f"><p local-id="df1fe76faac1">links are from reader&rsquo;s perspective--what are they probably looking for?</p></li><li local-id="f453f853d74c"><p local-id="117f8f3908a4">limited text content</p></li></ul><p local-id="51eb9a8100e6">You can increase readability by introducing multiple columns, pictures for &lsquo;hot&rsquo; pages, and headers to divide links by category.</p><p local-id="301646a45342">
<ac:structured-macro ac:name="excerpt-include" ac:schema-version="1" ac:local-id="09661e1d-ca12-4c35-998e-57c2f7e58a1e" ac:macro-id="76d3297e-f095-40a6-bfe2-a844d493fa42"><ac:parameter ac:name=""><ac:link><ri:page ri:content-title="Elements of 'beautiful,' effective pages" ri:version-at-save="10" /></ac:link></ac:parameter><ac:parameter ac:name="name">page best practices navbox</ac:parameter><ac:parameter ac:name="nopanel">true</ac:parameter></ac:structured-macro>
</p></ac:layout-cell></ac:layout-section></ac:layout>
"""


@dataclasses.dataclass(frozen=True)
class ContentDef:
    """Everything needed to build one page's raw content-API payload and
    the values we expect scrape_page_contents_from_server to produce for it."""

    key: str
    id: str
    version: int
    title: str
    last_modified: str  # ISO-ish string, as returned in version.createdAt
    html: str


CONTENT_DEFS: dict[str, ContentDef] = {
    cd.key: cd
    for cd in [
        ContentDef(
            key="stub_regression_report",
            id="123456",
            version=10,
            title="Regression report - patch 1.3",
            last_modified="2026-07-23T10:00:00.000Z",
            html=STUB_HTML_1,
        ),
        ContentDef(
            key="stub_sanity_and_regression_report",
            id="123457",
            version=4,
            title="Regression report - sanity + full",
            last_modified="2026-07-23T11:15:00.000Z",
            html=STUB_HTML_2,
        ),
        ContentDef(
            key="realistic_navbox_page",
            id="123458",
            version=6,
            title="Navboxes",
            last_modified="2026-03-04T18:53:01.000Z",
            html=REALISTIC_HTML_NAVBOX,
        ),
        ContentDef(
            key="realistic_landing_page",
            id="123459",
            version=20,
            title="Landing pages",
            last_modified="2026-06-30T08:45:24.000Z",
            html=REALISTIC_HTML_LANDING_PAGE,
        ),
    ]
}

ALL_PIDS = [cd.id for cd in CONTENT_DEFS.values()]


def raw_content_response_from_def(cd: ContentDef) -> dict:
    """Build a Confluence content-API payload from a ContentDef."""
    return {
        "id": cd.id,
        "title": cd.title,
        "version": {
            "number": cd.version,
            "createdAt": cd.last_modified,
        },
        "body": {
            "storage": {
                "value": cd.html,
            }
        },
    }


# Stand-in "server": pid -> raw payload, so the mocked request function can
# look pages up the same way the real endpoint would return them by id.
SERVER = {cd.id: raw_content_response_from_def(cd) for cd in CONTENT_DEFS.values()}


# ---------------------------------------------------------------------------
# Shared patching fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def content_calls(monkeypatch):
    """Patch request_page_contents and _store_page_contents, recording every
    call so chunking behavior (not just final output) can be asserted on."""
    request_calls = []  # list of pid-lists, one per call
    store_calls = []    # list of page-lists, one per call

    def fake_request(pids, strip_to_html=False):
        request_calls.append(list(pids))
        return [copy.deepcopy(SERVER[pid]) for pid in pids]

    def fake_store(pages):
        store_calls.append(copy.deepcopy(pages))

    monkeypatch.setattr(f"ccandle.pages.scrape_page_htmls.request_page_contents", fake_request)
    monkeypatch.setattr(f"ccandle.pages.scrape_page_htmls._store_page_contents", fake_store)

    return {"request_calls": request_calls, "store_calls": store_calls}


# ---------------------------------------------------------------------------
# Tests: field transformation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cd", list(CONTENT_DEFS.values()), ids=lambda cd: cd.key)
def test_page_fields_transformed_correctly(content_calls, cd):
    result = scrape_page_contents_from_server([cd.id])
    page = result[0]

    assert page["id"] == cd.id
    assert page["version"] == cd.version
    assert isinstance(page["version"], int)
    assert page["title"] == cd.title
    assert page["last_modified"] == cd.last_modified
    # HTML must pass through untouched -- no stripping/parsing at this stage.
    assert page["html"] == cd.html

# ---------------------------------------------------------------------------
# Tests: chunking behavior
# ---------------------------------------------------------------------------

def test_chunk_size_splits_requests_and_stores_into_batches(content_calls):
    scrape_page_contents_from_server(ALL_PIDS, chunk_size=2)

    assert content_calls["request_calls"] == [ALL_PIDS[0:2], ALL_PIDS[2:4]]
    assert len(content_calls["store_calls"]) == 2
    assert [p["id"] for p in content_calls["store_calls"][0]] == ALL_PIDS[0:2]
    assert [p["id"] for p in content_calls["store_calls"][1]] == ALL_PIDS[2:4]


def test_store_happens_incrementally_not_once_at_the_end(content_calls):
    # This is the behavior the "recovery isn't so nasty" comment is about:
    # if a chunk_size smaller than the pid list only ever produced ONE
    # store call at the end, a network failure partway through a large
    # sync would lose everything gathered so far. Guard against silently
    # regressing back to an all-in-one-go store.
    scrape_page_contents_from_server(ALL_PIDS, chunk_size=1)

    assert len(content_calls["store_calls"]) == len(ALL_PIDS)
    for call_pages in content_calls["store_calls"]:
        assert len(call_pages) == 1  # never batched into a bigger group than requested


def test_chunk_size_larger_than_pid_list_makes_a_single_chunk(content_calls):
    scrape_page_contents_from_server(ALL_PIDS, chunk_size=100)

    assert content_calls["request_calls"] == [ALL_PIDS]
    assert len(content_calls["store_calls"]) == 1


def test_chunk_size_exact_multiple_has_no_trailing_empty_chunk(content_calls):
    # 4 pids, chunk_size 2 -> exactly 2 chunks, not 2 real chunks plus a
    # stray empty third one.
    scrape_page_contents_from_server(ALL_PIDS, chunk_size=2)

    assert len(content_calls["request_calls"]) == 2
    assert len(content_calls["store_calls"]) == 2


def test_empty_pid_list_makes_no_network_or_store_calls(content_calls):
    result = scrape_page_contents_from_server([])

    assert result == []
    assert content_calls["request_calls"] == []
    assert content_calls["store_calls"] == []