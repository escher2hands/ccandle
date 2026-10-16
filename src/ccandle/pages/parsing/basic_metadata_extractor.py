# Get basic metadata on pages, so things like page classification can go smoothly.
# - link count
# - word count
# - image count
# - lead para
# - check if page has link tree
# Note that page typer has a far richer (and more resource heavy) breakdown of pages.
# However, most of those values are useless to humans, whereas these are directly
# usable metrics without the need for scaling and interpretation.
# additionally, we introduce an eval_notes field, marking pros or cons on the page
# formatting.
from ccandle.config.config_app import APP_HANDLE
from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.pages.parsing.eval_defs import *
from ccandle.pages.parsing.paragraph_parser import extract_lead_paragraph_from_soup
from ccandle.pages.parsing.parse_to_plain_text import extract_text_and_word_count_from_html, build_title_index
from ccandle.page_types.extract_type_signals import link_count_from_html, image_count_from_html, \
    macro_child_widget_from_html, header_count_from_soup, macro_has_toc_from_html, bullet_count_from_plain_text
import sqlite3, json
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from tqdm import tqdm
from bs4 import BeautifulSoup
from ccandle.presentation.theme import *

# Bulk process pages, extracting their basic metadata
# Passing an empty pid list will run on the entire db.
def add_basic_metadata_in_bulk(pids=None, path_to_db=PATH_DB, quiet=False):
    pids = pids or get_all_ids_in_pages(path_to_db=path_to_db)
    pages = _get_page_texts_and_data(pids, path_to_db=path_to_db)
    _exit_if_some_pages_are_unparsed(pages)         # short circuit exit if this step is run on a faulty db
    enriched_pages = []

    title_index, space_key_index = build_title_index(path_to_db) # required by extract_text_and_word_count_from_html.
                                                # As we don't want to reestablish this each loop, we create it once here

    for page in tqdm(pages, desc="Extracting basic metadata from each page...", unit="page", disable=quiet):
        soup = BeautifulSoup(page['html'], 'html.parser')
        lead_para_text, eval_notes = _get_eval_notes(page['html'], soup, page['plain_text'], page['space_id'], page['word_count'], title_index, space_key_index)
        enriched = {
            'id': page['id'],
            'link_count': link_count_from_html(page['html']),
            'image_count': image_count_from_html(page['html']),
            'lead_para': lead_para_text,
            'has_link_tree': eval_notes['has_link_tree'],
            'eval_notes': eval_notes['serialized_notes'],
        }
        enriched_pages.append(enriched)
    _store_enriched_metadata(enriched_pages, path_to_db=path_to_db)

# Process pages to get metadata relating to page quality.
# Notes definitions are in eval_defs.py, and are appended as they
# trigger, instead of having identical length lists per page.
# We additionally check if page has a link tree, as this affects
# whether it is a directory page / landing page or not.
def _get_eval_notes(html, soup, plain_text, space_id, word_count, title_index, space_key_dict):
    lead_para_html = extract_lead_paragraph_from_soup(soup)
    lead_para_text, lead_words = extract_text_and_word_count_from_html(lead_para_html, space_key_dict.get(str(space_id)), title_index)

    notes = []
    if word_count > WORDS_PER_PAGE_MAX:
        notes.append(NOTES_PAGE_TOO_LONG)
    header_count = header_count_from_soup(soup)
    if ((header_count > 0 and word_count / header_count > WORDS_PER_HEADER_MAX) or
            header_count == 0 and word_count > WORDS_PER_HEADER_MAX * 2):
        notes.append(NOTES_HEADERS_TOO_FEW)
    if word_count > WORDS_UNTIL_TOC and not macro_has_toc_from_html(html):
        notes.append(NOTES_TOC_MISSING)

    bullets = bullet_count_from_plain_text(plain_text) or 1     # the min words_until_toc guard means we can default to 1 with no issues
    if word_count > WORDS_UNTIL_TOC and word_count / bullets < WORDS_PER_BULLET_MIN:
        notes.append(NOTES_BULLETS_TOO_DENSE)
    if lead_words > PARA_LENGTH_MIN and link_count_from_html(lead_para_html) > PARA_LINKS_MIN:
        notes.append(NOTES_LEAD_PARA_GOOD)
    notes_data = {
        'has_link_tree': macro_child_widget_from_html(html),
        'serialized_notes': json.dumps(notes),
    }
    return lead_para_text, notes_data


def _get_page_texts_and_data(pids, path_to_db):
    placeholders = ",".join(["?"] * len(pids))

    with sqlite3.connect(path_to_db) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, html, space_id, plain_text, word_count "
                       f"FROM {TABLE_PAGES} WHERE id IN ({placeholders})", pids)
        return [
            {'id': pid, 'html': html, 'space_id': space_id, 'plain_text': plain_text, 'word_count': word_count}
            for pid, html, space_id, plain_text, word_count in cursor.fetchall()
        ]

def _store_enriched_metadata(enriched_records, path_to_db):
    with sqlite3.connect(path_to_db) as conn:
        cur = conn.cursor()
        cur.executemany(
            f"UPDATE {TABLE_PAGES} "
            f"SET link_count = ?, image_count = ?, lead_para = ?, has_link_tree = ?, eval_notes = ? "
            f"WHERE id = ?",
            [(rec['link_count'], rec['image_count'], rec['lead_para'], rec['has_link_tree'], rec['eval_notes'],
              rec['id']) for rec in enriched_records]
        )
        conn.commit()

# Print error message and exit if some page has not been processed
# by the previous step of plain text parsing.
def _exit_if_some_pages_are_unparsed(pages):
    missing = [p["id"] for p in pages if p["plain_text"] is None or p["word_count"] is None]
    if missing:
        # CLI MESSAGE
        print(f"{RED}" + "-" * WIDTH_NICE + "\n"
              f"Some of your pages were processed out of order.\n"
              f"{DIM}Probably, this was because of a sync that aborted before \n"
              f"the step {RESET}'parse_text'{RED}{DIM} could finish running.\n"
              f"Try:\n"
              f"{RESET}   {APP_HANDLE} sync --from-step 'parse_text'\n"
              f"{RED}{DIM}to rerun and correct any issues from partial processing.")
        exit(1)
