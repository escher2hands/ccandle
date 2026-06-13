# get link count, word count, image count, lead para, and check if page has link tree
from bs4 import BeautifulSoup
from pages.types.extract_type_signals import link_count_from_html, image_count_from_html, word_count_from_soup
import sqlite3
from config.config_db import PATH_DB, TABLE_PAGES

def add_basic_metadata_in_bulk(pids):
    pages = _get_page_texts_and_htmls(pids)
    enriched_pages = []
    for page in pages:
        soup = BeautifulSoup(page['html'], 'html.parser')
        enriched = {
            'id': page['id'],
            'word_count': word_count_from_soup(soup),
            'link_count': link_count_from_html(page['html']),
            'image_count': image_count_from_html(page['html']),
            'lead_para': "",
            'has_link_tree': False,
        }
        enriched_pages.append(enriched)

    _store_enriched_metadata(enriched_pages)

def _get_page_texts_and_htmls(pids):
    placeholders = ",".join(["?"] * len(pids))

    with sqlite3.connect(PATH_DB) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT id, html, plain_text FROM {TABLE_PAGES} WHERE id IN ({placeholders})", pids)
        return [
            {'id': id, 'html': html, 'plain_text': plain_text}
            for id, html, plain_text in cursor.fetchall()
        ]


def _store_enriched_metadata(enriched_records):
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.executemany(
            f"UPDATE {TABLE_PAGES} "
            f"SET word_count = ?, link_count = ?, image_count = ?, lead_para = ?, has_link_tree = ? "
            f"WHERE id = ?",
            [(rec['word_count'], rec['link_count'], rec['image_count'], rec['lead_para'], rec['has_link_tree'],
              rec['id']) for rec in enriched_records]
        )
        conn.commit()