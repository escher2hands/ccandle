# get link count, word count, image count, lead para, and check if page has link tree
from bs4 import BeautifulSoup

from ccandle.pages.parsing.eval_defs import *
from ccandle.pages.parsing.paragraph_parser import extract_lead_paragraph_from_soup
from ccandle.pages.parsing.plain_text_extractor import extract_text_and_word_count_from_html
from ccandle.pages.types.extract_type_signals import link_count_from_html, image_count_from_html, macro_child_widget_from_html, \
    header_count_from_soup, macro_has_toc_from_html
from ccandle.spaces.space_utils import get_space_attribute
import sqlite3, json
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from tqdm import tqdm


def add_basic_metadata_in_bulk(pids):
    pages = _get_page_texts_and_htmls(pids)
    enriched_pages = []
    for page in tqdm(pages, desc="Extracting basic metadata from each page...", unit="page"):
        soup = BeautifulSoup(page['html'], 'html.parser')
        lead_para_text, eval_notes = _get_eval_notes(page['html'], soup, page['space_id'], page['word_count'])
        enriched = {
            'id': page['id'],
            'link_count': link_count_from_html(page['html']),
            'image_count': image_count_from_html(page['html']),
            'lead_para': lead_para_text,
            'has_link_tree': eval_notes['has_link_tree'],
            'eval_notes': eval_notes['serialized_notes'],
        }
        enriched_pages.append(enriched)
    _store_enriched_metadata(enriched_pages)

def _get_eval_notes(html, soup, space_id, word_count):
    lead_para_html = extract_lead_paragraph_from_soup(soup)
    space_key = get_space_attribute(space_id, 'id', 'short_id')
    lead_para_text, lead_words = extract_text_and_word_count_from_html(lead_para_html, space_key)

    notes = []
    if word_count > WORDS_PER_PAGE_MAX:
        notes.append(NOTES_PAGE_TOO_LONG)
    header_count = header_count_from_soup(soup)
    if (header_count > 0 and (word_count / header_count_from_soup(soup))) or (word_count > WORDS_PER_HEADER_MAX * 2):
        notes.append(NOTES_HEADERS_TOO_FEW)
    if word_count > WORDS_UNTIL_TOC and not macro_has_toc_from_html(html):
        notes.append(NOTES_TOC_MISSING)
    if lead_words > PARA_LENGTH_MIN and link_count_from_html(lead_para_html) > PARA_LINKS_MIN:
        notes.append(NOTES_LEAD_PARA_GOOD)
    notes_data = {
        'has_link_tree': macro_child_widget_from_html(html),
        'serialized_notes': json.dumps(notes),
    }
    return lead_para_text, notes_data


def _get_page_texts_and_htmls(pids):
    placeholders = ",".join(["?"] * len(pids))

    with sqlite3.connect(PATH_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, html, space_id, plain_text, word_count "
                       f"FROM {TABLE_PAGES} WHERE id IN ({placeholders})", pids)
        return [
            {'id': pid, 'html': html, 'space_id': space_id, 'plain_text': plain_text, 'word_count': word_count}
            for pid, html, space_id, plain_text, word_count in cursor.fetchall()
        ]

def _store_enriched_metadata(enriched_records):
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.executemany(
            f"UPDATE {TABLE_PAGES} "
            f"SET link_count = ?, image_count = ?, lead_para = ?, has_link_tree = ?, eval_notes = ? "
            f"WHERE id = ?",
            [(rec['link_count'], rec['image_count'], rec['lead_para'], rec['has_link_tree'], rec['eval_notes'],
              rec['id']) for rec in enriched_records]
        )
        conn.commit()