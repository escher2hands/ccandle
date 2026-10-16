# Derives the plain text of a Confluence page from its storage-format HTML, in ONE pass.
# - headings
# - links in line, resolved to page ids where the target pid is in the corpus
# - bullet points respected
# - excerpts from other pages replaced with a reference to the page they excerpt
# - true word count
#
# plain_text, word_count and links_list are all written here and nowhere else.
# plain_text is a pure function of (html, corpus title index), so re-running this step
# alone on any subset of pages is always consistent (the index always covers the full corpus).
#
# Link markers are defined in link_markers.py:
#   [[link to: KEY:PID]]          target is in the corpus
#   [[ulink to: KEY:Some Title]]  target isn't tracked; title only

import json
import sqlite3

from bs4 import BeautifulSoup, CData, NavigableString, Tag
from tqdm import tqdm

from ccandle.config.config_db import TABLE_PAGES
from ccandle.db.db_query_utils import query_db_results
from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.spaces.space_utils import dict_space_keys_by_id
from ccandle.pages.parsing.link_marker_defs import iter_markers, render_marker, strip_markers

# --- Confluence-specific HTML element identifiers ---
MACRO_FALLBACK_TAG = "ac:adf-fallback"
STRUCTURED_MACRO_TAG = "ac:structured-macro"
EXCERPT_INCLUDE_MACRO = "excerpt-include"
LINK_TAG = "ac:link"
LINK_BODY_TAGS = ["ac:link-body", "ac:plain-text-link-body"]
PAGE_LINK_TAG = "ri:page"
CONTENT_TITLE_ATTR = "ri:content-title"
SPACE_KEY_ATTR = "ri:space-key"
MACRO_NAME_ATTR = "ac:name"

BLOCK_ELEMENTS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre"]
HEADING_ELEMENTS = {"h1", "h2"}
LIST_ITEM_ELEMENT = "li"

# Inline formatting: text on either side of these tags is joined exactly as the author
# typed it (so "co-<em>operate</em>" stays one word and "<b>bold</b>," keeps its comma).
# Any other tag (cells, br, macros, unknown) is treated as a separator and gets a space.
INLINE_TAGS = {
    "a", "abbr", "b", "big", "cite", "code", "del", "em", "font", "i", "ins", "kbd",
    "mark", "q", "s", "small", "span", "strike", "strong", "sub", "sup", "time",
    "tt", "u", "var", "ac:inline-comment-marker",
}
TEXT_NODE_TYPES = (NavigableString, CData)  # same node types bs4's get_text() reads

# A link with no explicit body renders as the target's title in Confluence, so by default
# we show that title as the link's visible text (and count it as words).
BARE_LINK_SHOWS_TITLE = True


# Bulk entry point for sync_all(). Does not hit any API; all local.
# pid_list=None means every page. Ids are accepted as str or int, always written as str.
def extract_plain_texts_in_bulk(pid_list=None, quiet=False, *, path_to_db):
    pids = pid_list or get_all_ids_in_pages(path_to_db=path_to_db)  # get all pages if none specified
    pids = [str(pid) for pid in pids]  # force all PIDs to be strings

    title_index, space_keys = build_title_index(path_to_db)

    rows = query_db_results(select_query="id, html, space_id", path_to_db=path_to_db)
    records = [
        {"id": str(pid), "html": html, "space_key": space_keys.get(str(space_id))}
        for pid, html, space_id in rows
        if str(pid) in pids
    ]

    texts = []
    for record in tqdm(records, desc="Extracting plain text from bulk", unit="page", disable=quiet):
        text, word_count = extract_text_and_word_count_from_html(
            html=record["html"], space_key=record["space_key"], title_index=title_index
        )
        texts.append({
            "id": record["id"],
            "text": text,
            "word_count": word_count,
            "links_list": json.dumps([m.entry for m in iter_markers(text)]),
        })

    _store_plain_texts_in_bulk(texts, path_to_db=path_to_db)
    return texts


# Walks block-level elements in document order and converts them to plain text:
# - Headings (h1/h2) become [[Heading: ...]]
# - List items get a dash prefix
# - All other blocks are extracted as-is
# Skips nested blocks to avoid double-processing, and deduplicates across the doc.
# title_index=None means no link can resolve (every link comes out as a ulink).
def extract_text_and_word_count_from_html(html: str, space_key, title_index=None) -> tuple[str, int]:
    if not html:
        return "", 0

    soup = clean_confluence_html(html, space_key=space_key, title_index=title_index)

    output = []
    seen = set()
    word_count = 0

    def add_if_new(display_text: str) -> bool:
        display_text = display_text.strip()
        if display_text and display_text not in seen:
            seen.add(display_text)
            output.append(display_text)
            return True
        return False

    for el in soup.find_all(BLOCK_ELEMENTS, recursive=True):
        if _is_nested_block(el):
            continue

        text = _text_of(el)

        if el.name in HEADING_ELEMENTS:
            added = add_if_new(f"[[Heading: {text}]]")
        elif el.name == LIST_ITEM_ELEMENT:
            added = add_if_new(f"- {text}")
        else:
            added = add_if_new(text)

        if added:  # markers aren't words
            word_count += len(strip_markers(text).split())

    return "\n".join(output).strip(), word_count


def _store_plain_texts_in_bulk(text_records, path_to_db):
    with sqlite3.connect(path_to_db) as conn:  # commits on success
        conn.executemany(
            f"UPDATE {TABLE_PAGES} SET plain_text = ?, word_count = ?, links_list = ? WHERE id = ?",
            [(r["text"], r["word_count"], r["links_list"], r["id"]) for r in text_records],
        )


# ---------------------------------------------------------------------------
# Corpus title index: {(space_key, title): pid}, normalized, built from the DB
# ---------------------------------------------------------------------------

def _normalized_title(title) -> str:
    return " ".join(str(title).split()).casefold()

def _normalized_space(space_key) -> str:
    return str(space_key).strip().casefold()

# Returns {(normalized space key, normalized title): pid_str} for every page in the DB, AND
# {space_id: space_key} for every tracked space.
# Pages whose space key can't be determined are left out (nothing could link to them by key).
def build_title_index(path_to_db):
    space_keys = dict_space_keys_by_id()        # fetch a dict with all space short_ids, indexed by space ID

    index = {}
    for pid, title, space_id in query_db_results(select_query="id, title, space_id", path_to_db=path_to_db):
        space_key = space_keys.get(str(space_id))
        if title is None or not space_key:
            continue
        index[(_normalized_space(space_key), _normalized_title(title))] = str(pid)
    return index, space_keys


# Text of an element with whitespace normalized to single spaces. Text nodes are joined
# exactly as written when only inline formatting tags sit between them; anything else
# (table cells, <br>, macros, nested blocks) is a boundary and gets a space.
def _text_of(el) -> str:
    parts = []

    def walk(node):
        for child in node.children:
            if type(child) in TEXT_NODE_TYPES:
                parts.append(str(child))
            elif isinstance(child, Tag):
                if child.name in INLINE_TAGS:
                    walk(child)
                else:
                    parts.append(" ")
                    walk(child)
                    parts.append(" ")

    walk(el)
    return " ".join("".join(parts).split())


# ---------------------------------------------------------------------------
# HTML cleaning
# ---------------------------------------------------------------------------

# Parses and cleans Confluence HTML:
#   - Removes ADF fallback tags (duplicated macro content)
#   - Replaces excerpt-include macros with readable placeholders
#   - Replaces page links with their visible text plus a link marker
#   - Strips tags that contribute no text content
def clean_confluence_html(html: str, space_key=None, title_index=None) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")

    _remove_adf_fallbacks(soup)
    _replace_excerpt_include_macros(soup)
    _replace_internal_links(soup, space_key, title_index or {})
    _strip_empty_tags(soup)

    return soup


# Drops ac:adf-fallback tags, which duplicate macro content as HTML fallbacks.
def _remove_adf_fallbacks(soup: BeautifulSoup) -> None:
    for fallback in soup.find_all(MACRO_FALLBACK_TAG):
        fallback.decompose()


# Replaces excerpt-include macros with a plain text placeholder.
# These macros transclude content from other pages, which we can't
# inline, so we leave a readable marker instead.
def _replace_excerpt_include_macros(soup: BeautifulSoup) -> None:
    macros = soup.find_all(STRUCTURED_MACRO_TAG, {MACRO_NAME_ATTR: EXCERPT_INCLUDE_MACRO})
    for macro in macros:
        page_link = macro.find(PAGE_LINK_TAG)
        page_title = (
            page_link.get(CONTENT_TITLE_ATTR, "Unknown page")
            if page_link
            else "Unknown page"
        )
        placeholder = soup.new_tag("p")
        placeholder.string = f"[[Excerpt from: {page_title}]]"
        macro.replace_with(placeholder)


# Replaces each <ac:link> that targets a page with "visible text + marker".
# Links to attachments, users, or in-page anchors have no ri:page and are left alone.
# Attribute values arrive already unescaped from the parser (Q&amp;A -> Q&A).
def _replace_internal_links(soup: BeautifulSoup, default_space_key, title_index: dict) -> None:
    for link in soup.find_all(LINK_TAG):
        page = link.find(PAGE_LINK_TAG)
        title = page.get(CONTENT_TITLE_ATTR) if page else None
        if not title:
            continue

        # Confluence: no explicit space key means the same space as the linking page
        target_space = page.get(SPACE_KEY_ATTR) or default_space_key
        pid = (
            title_index.get((_normalized_space(target_space), _normalized_title(title)))
            if target_space
            else None
        )
        marker = render_marker(target_space, pid or title, resolved=pid is not None)

        body = link.find(LINK_BODY_TAGS)
        if body is not None:
            visible = body.get_text(" ", strip=True)
        else:
            visible = title if BARE_LINK_SHOWS_TITLE else ""

        link.replace_with(NavigableString(f"{visible} {marker}".strip()))


# Removes tags that contribute no text. Only empty inline tags (e.g. empty formatting
# spans) vanish outright, since "foo<span></span>bar" really is "foobar". Anything else
# without text (<br>, empty cells, a space inside a span) becomes a single space, because
# it separates the text around it: "line<br>break" must not collapse into "linebreak".
def _strip_empty_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all():
        if tag.decomposed:  # already removed along with an empty ancestor
            continue
        if not tag.get_text(strip=True):
            if tag.name in INLINE_TAGS and not tag.get_text():
                tag.decompose()
            else:
                tag.replace_with(NavigableString(" "))


# Returns True if this element is already inside another block-level element.
def _is_nested_block(el) -> bool:
    return bool(el.find_parent(BLOCK_ELEMENTS))