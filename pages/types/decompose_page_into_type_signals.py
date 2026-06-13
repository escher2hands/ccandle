from bs4 import BeautifulSoup
from db.db_query_utils import query_field_multi_in_pages
from pages.types.extract_type_signals import *
from presentation.theme import DIM, BOLD, RESET, WIDTH_NICE
import json, numpy as np


def decompose_page(page_id, verbose=False):
    signals_dict = {}
    title, html, plain_text, word_count = query_field_multi_in_pages(page_id, 'title',
                                                                         'html', 'plain_text', 'word_count')
    if verbose:
        print("=" * WIDTH_NICE)
        print(page_id + " | " + title.upper() + "\n")

    if word_count is None or word_count == 0:
        if verbose: print("Empty page. No words. Skipping.")
        return _empty_signals_vector()

    soup = BeautifulSoup(html, 'html.parser')

    signals = kw_signals(title, soup, html, plain_text)
    _print_signals_if_verbose(signals, "keyword signals:", verbose)
    signals_dict.update(signals)

    signals = date_pattern_in_title(title)
    _print_signals_if_verbose(signals, "title has date signals:", verbose)
    signals_dict.update(signals)

    metric_flags, title = query_field_multi_in_pages(page_id, 'metrics_json', 'title')
    signals = metric_flag_signals(json.loads(metric_flags))
    _print_signals_if_verbose(signals, "page eval metric flags:", verbose)
    signals_dict.update(signals)

    word_count, image_count = query_field_multi_in_pages(page_id, 'word_count', 'image_count')
    link_count = link_count_from_html(html)
    signals = base_content_signals(word_count, image_count, link_count, soup, html, plain_text)
    _print_signals_if_verbose(signals, "base stats (proportional to word count)", verbose)
    signals_dict.update(signals)
    signals = aggregate_table_signals(html, soup)
    _print_signals_if_verbose(signals, "table_signals:", verbose)
    signals_dict.update(signals)
    
    signals = aggregate_macro_signals(html)
    _print_signals_if_verbose(signals, "macro signals:", verbose)
    signals_dict.update(signals)

    return signals_dict

def base_content_signals(word_count, image_count, link_count, soup, html, plain_text):
    mention_count = macro_mentions_count_from_html(html)
    word_count_div = (word_count / 100) or 1
    para_stats = paragraph_length_signals_from_soup(soup)
    return {
        'word_count': word_count,
        'image_count': image_count,
        'link_count': link_count,
        'link_git_count': link_gitlab_count_from_html(html),
        'link_jira_count': link_jira_count_from_html(html),
        'image_density': (image_count / word_count_div),
        'link_density': (link_count / word_count_div),
        'task_count': macro_tasks_count_from_html(html),
        'mentions_count': mention_count,
        'mention_density': mention_count / word_count_div,
        'diagram_count': diagram_count_from_html(html),
        'bullet_count': bullet_count_from_html(html),
        'header_count': header_count_from_soup(soup),
        'digit_to_letter_ratio': digit_to_letter_ratio_from_text(plain_text),
        'para_count': para_stats['count'],
        'para_longest': para_stats['longest'],
        'para_share_long': para_stats['share_long'],
        'para_share_short': para_stats['share_short'],
        'para_average': para_stats['average'],
    }

def metric_flag_signals(metrics_json):
    from metadata_defs.label_defs_all import ALL_METRIC_FLAGS
    # Convert input to a set (handles list input directly)
    present = set(metrics_json or [])
    return {flag: int(flag in present) for flag in ALL_METRIC_FLAGS}

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
    signal_keys = [
        't_month', 't_g_meeting_minutes', 't_meeting_minutes', 't_g_workshop_minutes', 't_workshop_minutes',
        't_release', 't_performance', 't_anti_landing', 't_intro', 't_anti_intro', 't_solution',
        'h_solution',
        'b_meeting_minutes', 'b_workshop', 'b_g_release', 'b_release', 'b_anti_release', 'b_performance',
        'b_anti_performance', 'b_bug', 'date', 'date_bad', 'date_reverse', 'bot-image-none', 'bot-image-few',
        'bot-image-dense', 'bot-landing-page-candidate', 'bot-landing-page', 'bot-add-link-tree',
        'bot-add-page-summary', 'bot-split-to-content-page', 'bot-lead-para-missing',
        'bot-lead-para-links-limited', 'bot-lead-para-long', 'bot-lead-para-good', 'bot-links-limited',
        'bot-links-few', 'bot-links-good', 'bot-links-dense', 'bot-page-length-empty', 'bot-page-length-stub',
        'bot-page-length-short', 'bot-page-length-medium', 'bot-page-length-long',
        # base_content_signals
        'word_count', 'image_count', 'link_count', 'link_git_count', 'link_jira_count',
        'image_density', 'link_density', 'task_count', 'mentions_count', 'mention_density',
        'diagram_count', 'bullet_count', 'header_count', 'digit_to_letter_ratio',
        'para_count', 'para_longest', 'para_share_long', 'para_share_short', 'para_average',
        # aggregate_table_signals
        'table_count', 'minutes_in_tables', 'word_count_outside_tables',
        'diagram_outside_tables', 'img_outside_tables',
        'sig_table_has_cells', 'sig_cell_share_low_words', 'sig_cell_share_empty',
        'sig_table_long_cell', 'sig_cell_many',
        # aggregate_macro_signals
        'macro_toc', 'macro_jira_query',
        'macro_struct_total', 'macro_panels', 'macro_expandables', 'macro_excerpts',
    ]
    SIGNALS_VECTOR_DIM = 80
    assert len(signal_keys) == SIGNALS_VECTOR_DIM, f"Got {len(signal_keys)}, expected {SIGNALS_VECTOR_DIM}"
    return {key: 0 for key in signal_keys}

def inspect_page_type_signals():
    import sqlite3
    from config.config_db import PATH_DB, TABLE_PAGES
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        smell_type = 'eval_smell'
        cur.execute(f"""SELECT id, {smell_type} FROM {TABLE_PAGES}""")
        rows = cur.fetchall()
    page_ids = [row[0] for row in rows]
    smell_scores = [row[1] for row in rows]
    return page_ids, smell_scores
