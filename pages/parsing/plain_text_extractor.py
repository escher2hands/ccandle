# goal here is to derive the plain text of a Confluence page, using its HTML.
# we add a bit of value beyond just stripping with beautiful soup:
# - headings
# - links in line
# - bullet points should be respected
from bs4 import BeautifulSoup
from tqdm import tqdm

from db.db_query_utils import query_db_results
from db.db_utils import get_all_ids_in_pages
from spaces.space_utils import get_space_attribute
import re

# --- Confluence-specific HTML element identifiers ---
MACRO_FALLBACK_TAG = "ac:adf-fallback"
STRUCTURED_MACRO_TAG = "ac:structured-macro"
EXCERPT_INCLUDE_MACRO = "excerpt-include"
PAGE_LINK_TAG = "ri:page"
CONTENT_TITLE_ATTR = "ri:content-title"
MACRO_NAME_ATTR = "ac:name"

BLOCK_ELEMENTS = ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "table", "pre"]
HEADING_ELEMENTS = {"h1", "h2"}
LIST_ITEM_ELEMENT = "li"
INTERNAL_LINK_FLAG_PATTERN = re.compile(r"\[\[link to:\s+(~[A-Za-z0-9]+|[A-Z0-9]+):(.*?)\]\]", re.DOTALL,)

def extract_plain_texts_in_bulk(pid_list=None):
    pids = pid_list or get_all_ids_in_pages()
    all_pids_to_htmls = [
        {
            'id': result[0],
            'html': result[1],
            'space_key': get_space_attribute(result[2], "id", "short_id"),
        } for result in query_db_results(select_query="id, html, space_id")]
    pids_to_htmls = [record for record in all_pids_to_htmls if record['id'] in pids]

    texts = []
    for record in tqdm(pids_to_htmls, desc="Extracting plain text from bulk", unit="page"):
        text, word_count = extract_text_and_word_count_from_html(html=record['html'], space_key=record['space_key'])
        texts.append({
            'id': record['id'],
            'text': text,
            'word_count': word_count,
        })

    _store_plain_texts_in_bulk(texts)
    return texts

# Walks block-level elements in document order and converts them to plain text:
#   - Headings become [[Heading: ...]]
#   - List items get a dash prefix
#   - All other blocks are extracted as-is
# Skips nested blocks to avoid double-processing, and deduplicates across the doc.
def extract_text_and_word_count_from_html(html: str, space_key: str) -> tuple[str, int]:
    if not html:
        return "", 0

    html = _insert_internal_link_flags(html, space_key)     # insert link tags for later metrics
    soup = clean_confluence_html(html)                      # get soup for easier page decomposition

    output = []
    seen = set()
    word_count = 0

    def add_if_new(display_text: str, count_text: str) -> None:
        nonlocal word_count
        display_text = display_text.strip()
        if display_text and display_text not in seen:
            seen.add(display_text)
            output.append(display_text)
            count_text = INTERNAL_LINK_FLAG_PATTERN.sub("", count_text)
            word_count += len(count_text.split())

    for el in soup.find_all(BLOCK_ELEMENTS, recursive=True):
        if _is_nested_block(el):
            continue

        text = el.get_text(" ", strip=True)

        if el.name in HEADING_ELEMENTS:
            add_if_new(f"[[Heading: {text}]]", text)
        elif el.name == LIST_ITEM_ELEMENT:
            add_if_new(f"- {text}", text)
        else:
            add_if_new(text, text)

    return "\n".join(output).strip(), word_count

def _store_plain_texts_in_bulk(text_records):
    import sqlite3
    from config.config_db import PATH_DB, TABLE_PAGES
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.executemany(
            f"UPDATE {TABLE_PAGES} SET plain_text = ?, word_count = ? WHERE id = ?",
            [(record['text'], record['word_count'], record['id']) for record in text_records]
        )
        conn.commit()

#     Parses and cleans Confluence HTML:
#       - Removes ADF fallback tags (duplicated macro content)
#       - Replaces excerpt-include macros with readable placeholders
#       - Strips tags that contribute no text content
#     Returns a cleaned BeautifulSoup object.
def clean_confluence_html(html: str) -> BeautifulSoup:
    soup = BeautifulSoup(html or "", "html.parser")

    _remove_adf_fallbacks(soup)
    _replace_excerpt_include_macros(soup)
    _strip_empty_tags(soup)

    return soup

# Drops ac:adf-fallback tags, which duplicate macro content as HTML fallbacks.
def _remove_adf_fallbacks(soup: BeautifulSoup) -> None:
    for fallback in soup.find_all(MACRO_FALLBACK_TAG):
        fallback.decompose()

# Replaces excerpt-include macros with a plain text placeholder.
# These macros transclude content from other pages, which we can't
# inline — so we leave a readable marker instead.
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

# Removes tags that contain no visible text (e.g. empty formatting spans).
def _strip_empty_tags(soup: BeautifulSoup) -> None:
    for tag in soup.find_all():
        if not tag.get_text(strip=True):
            tag.decompose()

def _insert_internal_link_flags(html, default_space_key="UNKNOWN") -> str:
    pattern = re.compile(r"<ac:link\b[^>]*>(?:[^<]|<(?!/ac:link>))*?</ac:link>",flags=re.DOTALL)

    def _replace(match):
        link_tag = match.group(0)
        title_match = re.search(r'ri:content-title="([^"]+)"', link_tag)
        if not title_match:
            return link_tag  # nothing we can do
        space_match = re.search(r'ri:space-key="([^"]+)"', link_tag)
        space_key = (space_match.group(1)   if space_match   else default_space_key)

        # If we *still* don't have a space key, leave unqualified
        if space_key:
            target = f"{space_key}:{title_match.group(1)}"
        else:
            target = title_match.group(1)

        return link_tag + f"[[link to: {target}]]"

    return pattern.sub(_replace, html)

# Returns True if this element is already inside another block-level element.
def _is_nested_block(el) -> bool:
    return bool(el.find_parent(BLOCK_ELEMENTS))
