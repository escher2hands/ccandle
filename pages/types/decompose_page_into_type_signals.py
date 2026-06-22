from bs4 import BeautifulSoup
from config.config_db import TABLE_VECTORS
from db.db_query_utils import query_field_multi_in_pages
from db.db_utils import get_all_ids_in_pages
from db.table_utils import create_table
from pages.types.extract_type_signals import *
from pages.types.type_signals_scaler import scale_signal_vectors
from pages.types.type_signals_defs import SIGNAL_KEYS, SIGNALS_VECTOR_DIM, THRESH_PAGE_EMPTY
from pages.vectors.schema_table_vectors import SCHEMA_VECTORS
from presentation.theme import DIM, BOLD, RESET, WIDTH_NICE
import json, numpy as np
import sqlite3
from config.config_db import PATH_DB, TABLE_PAGES
from tqdm import tqdm

def generate_signal_vectors_in_bulk(pids=None):
    page_ids = pids or get_all_ids_in_pages()
    X = []

    for page_id in tqdm(page_ids, desc="Generating type signal vectors...", unit="pages"):
        sig_vec = get_decomposition_vector(page_id)
        X.append(sig_vec)

    X = np.array(X, dtype=float)
    X_scaled = scale_signal_vectors(X, SIGNAL_KEYS)

    create_table(TABLE_VECTORS, SCHEMA_VECTORS)     # create the table if it doesn't already exist

    _store_type_signal_vectors(page_ids, X, X_scaled)

def get_decomposition_vector(page_id):
    signals_dict = decompose_page(page_id, verbose=False)
    return np.array(list(signals_dict.values()), dtype=float)

def decompose_page(page_id, verbose=False):
    signals_dict = {}
    title, html, plain_text, word_count = query_field_multi_in_pages(page_id, 'title',
                                                                         'html', 'plain_text', 'word_count')
    if verbose:
        print("=" * WIDTH_NICE)
        print(page_id + " | " + title.upper() + "\n")

    if word_count is None or word_count < THRESH_PAGE_EMPTY:
        if verbose:
            if word_count == 0: print("Empty page. No words. Skipping.")
            else:               print("Stub page. Too few words to analyze. Skipping.")
        return _empty_signals_vector()

    soup = BeautifulSoup(html, 'html.parser')

    word_count, image_count, link_count, child_list = query_field_multi_in_pages(page_id,
                                              'word_count', 'image_count', 'link_count', 'child_list')
    signals = base_content_signals(word_count, image_count, soup, html, plain_text)
    _print_signals_if_verbose(signals, "base signals (proportional to word count)", verbose)
    signals_dict.update(signals)

    signals = paragraph_signals(soup)
    _print_signals_if_verbose(signals, "paragraph signals", verbose)
    signals_dict.update(signals)

    child_count = len(json.loads(child_list))
    signals = connectedness_signals(word_count, link_count, child_count, html)
    _print_signals_if_verbose(signals, "connectedness signals", verbose)
    signals_dict.update(signals)

    signals = aggregate_table_signals(html, soup)
    _print_signals_if_verbose(signals, "table signals", verbose)
    signals_dict.update(signals)

    signals = lexicographic_signals_from_plain_text(plain_text)
    _print_signals_if_verbose(signals, "lexicographic signals", verbose)
    signals_dict.update(signals)
    
    signals = aggregate_macro_signals(html)
    _print_signals_if_verbose(signals, "macro signals", verbose)
    signals_dict.update(signals)

    signals = macro_code_block_signals_from_soup(soup)
    _print_signals_if_verbose(signals, "code block signals", verbose)
    signals_dict.update(signals)

    signals = kw_signals(title, soup, plain_text)
    _print_signals_if_verbose(signals, "keyword signals", verbose)
    signals_dict.update(signals)

    signals = date_pattern_in_title(title)
    _print_signals_if_verbose(signals, "title has date signals", verbose)
    signals_dict.update(signals)

    # metric_flags, title = query_field_multi_in_pages(page_id, 'metrics_json', 'title')
    signals = {"metric_flags": 0} #metric_flag_signals(json.loads(metric_flags))
    _print_signals_if_verbose(signals, "page evaluation metric signals", verbose)
    signals_dict.update(signals)

    # ensure we're not putting any malformed vectors in
    assert len(signals_dict) == SIGNALS_VECTOR_DIM, f"Got {len(signals_dict)}, expected {SIGNALS_VECTOR_DIM}"
    return signals_dict

def base_content_signals(word_count, image_count, soup, html, plain_text):
    mention_count = macro_mentions_count_from_html(html)
    word_count_div = (word_count / 100) or 1

    return {
        'word_count': word_count,
        'image_count': image_count,
        'image_density': (image_count / word_count_div),
        'task_count': macro_tasks_count_from_html(html),
        'mentions_count': mention_count,
        'mention_density': mention_count / word_count_div,
        'diagram_count': diagram_count_from_html(html),
        'bullet_count': bullet_count_from_html(html),
        'header_count': header_count_from_soup(soup),
        'digit_to_letter_ratio': digit_to_letter_ratio_from_text(plain_text),
    }

def paragraph_signals(soup):
    para_stats = paragraph_length_signals_from_soup(soup)
    lead_para_stats = paragraph_lead_signals_from_soup(soup)
    return {
        'para_count': para_stats['count'],
        'para_longest': para_stats['longest'],
        'para_share_long': para_stats['share_long'],
        'para_share_short': para_stats['share_short'],
        'para_average': para_stats['average'],
        'para_lead_good': lead_para_stats['good_lead_para'],
        'para_lead_words': lead_para_stats['word_count'],
        'para_lead_links': lead_para_stats['link_count'],
    }

def connectedness_signals(word_count, link_count, child_count, html):
    word_count_div = (word_count / 100) or 1
    return {
        'link_count': link_count,
        'link_git_count': link_gitlab_count_from_html(html),
        'link_jira_count': link_jira_count_from_html(html),
        'link_density': (link_count / word_count_div),
        'child_count': child_count,
    }

def metric_flag_signals(metrics_json):
    # from metadata_defs.label_defs_all import ALL_METRIC_FLAGS
    # Convert input to a set (handles list input directly)
    present = set(metrics_json or [])
    return None # {flag: int(flag in present) for flag in ALL_METRIC_FLAGS}

def aggregate_table_signals(html, soup):
    cell_sigs = table_cell_signature_stats_from_soup(soup)
    outside_table_media = table_diagram_and_image_counts_outside_from_soup(soup)
    return {
        'table_count': table_count_from_html(html),
        'minutes_in_tables': table_minutes_text_count_from_soup(soup),
        'word_count_outside_tables': table_word_count_outside_from_soup(soup),
        'diagram_outside_tables': outside_table_media['diagrams'],
        'img_outside_tables': outside_table_media['images'],
        'sig_table_has_cells': cell_sigs['has_cells'],
        'sig_cell_share_low_words': cell_sigs['share_short'],
        'sig_cell_share_empty': cell_sigs['share_empty'],
        'sig_table_long_cell': cell_sigs['has_long_cells'],
        'sig_cell_many': cell_sigs['has_many_cells'],
    }

def aggregate_macro_signals(html):
    macros_struct = macro_structures_signals_from_html(html)
    return {
        'macro_toc': macro_has_toc_from_html(html),
        'macro_jira_query': macro_has_jira_query_widget_from_html(html),
        'macro_struct_total': macros_struct['total'],
        'macro_panels': macros_struct['panels'],
        'macro_expandables': macros_struct['expandables'],
        'macro_excerpts': macros_struct['excerpts'],
        'macro_decisions': macros_struct['decisions'],
        'macro_children': macros_struct['child_widget'],
    }

def _print_signals(signals):
    for signal in signals:
        val = signals[signal]
        if val != 0:
            print(f"{signal:<26}: {val:>8.3f}")
        else:
            print(f"{DIM}{signal:<26}: {val:>8.3f}{RESET}")

def _print_signals_if_verbose(signals, message, verbose):
    if verbose:
        print('-' * WIDTH_NICE)
        print(f"{BOLD}{message}{RESET}\n")
        _print_signals(signals)
        print()


def _empty_signals_vector():
    assert len(SIGNAL_KEYS) == SIGNALS_VECTOR_DIM, f"Got {len(SIGNAL_KEYS)}, expected {SIGNALS_VECTOR_DIM}"
    return {key: 0 for key in SIGNAL_KEYS}

def inspect_page_type_signals():
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        smell_type = 'eval_smell'
        cur.execute(f"""SELECT id, {smell_type} FROM {TABLE_PAGES}""")
        rows = cur.fetchall()
    page_ids = [row[0] for row in rows]
    smell_scores = [row[1] for row in rows]
    return page_ids, smell_scores

def _store_type_signal_vectors(page_ids, signal_vec_unscaled, signal_vectors):
    rows = [
        (page_id, signal_vec_unscaled[i].astype(np.float32).tobytes(), signal_vectors[i].astype(np.float32).tobytes())
        for i, page_id in enumerate(page_ids)
    ]
    with sqlite3.connect(PATH_DB) as conn:
        conn.executemany(
            f"""INSERT INTO {TABLE_VECTORS} (id, type_signals_unscaled, type_signals_vec)
                VALUES (?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET type_signals_unscaled = excluded.type_signals_unscaled, 
                type_signals_vec = excluded.type_signals_vec""",
            rows,
        )

def load_type_signal_vectors():
    with sqlite3.connect(PATH_DB) as conn:
        rows = conn.execute(
            f"SELECT id, type_signals_vec FROM {TABLE_VECTORS} WHERE type_signals_vec IS NOT NULL"
        ).fetchall()

    pids = [row[0] for row in rows]
    X = np.array([
        np.frombuffer(row[1], dtype=np.float32)
        for row in rows
    ])
    return pids, X

