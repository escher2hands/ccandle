# basic sanity check on some test pages
from bs4 import BeautifulSoup
from ccandle.db.db_utils import get_field_in_pages
from ccandle.pages.types.extract_type_signals import header_count_from_soup, image_count_from_html, word_count_from_soup, \
    paragraph_length_signals_from_soup, link_count_from_html

TEST_DATA = {
    2850103315:
    {
        'title': "LANTERN — BULK KM TOOLS FOR CONFLUENCE CLOUD",
        'headings': 5,
        'para_count': 13,
        'para_longest': 247,  # from pasting paragraph text from browser to a word counter
        'link_count': 10,
        'image_count': 3,
        'word_count': 867,  # from pasting extracted plain_text to a word counter
    },
    2841291896:
    {
        'title': "'ADMINISTRATIVE' VS 'CONTENT' PAGES — UNDERSTANDING KINDS OF CONFLUENCE PAGES",
        'headings': 3,
        'para_count': 8,
        'para_longest': 73,
        'link_count': 3,
        'image_count': 4,
        'word_count': 235,
    },
}

def test_basic_page_metrics_and_parsing_algos(expected_metrics=TEST_DATA):
    html_by_pid = _get_htmls_with_pids()
    for pid, metrics in expected_metrics.items():
        print("-" * 80)
        print(f"PAGE ID: {pid}")
        html = html_by_pid[pid]
        soup = BeautifulSoup(html, 'html.parser')
        assert header_count_from_soup(soup) == metrics['headings']

        assert link_count_from_html(html) == metrics['link_count']
        assert image_count_from_html(html) == metrics['image_count']
        print(f"DEBUG: algo {word_count_from_soup(soup)} | canonical: {metrics['word_count']}")
        assert _same_length(word_count_from_soup(soup), metrics['word_count'])

        para_stats = paragraph_length_signals_from_soup(soup)
        assert para_stats['count'] == metrics['para_count']
        print(f"DEBUG: algo {para_stats['longest']} | canonical: {metrics['para_longest']}")
        assert _same_length(para_stats['longest'], metrics['para_longest'])     # as word count algos differ

    return 0

def _get_htmls_with_pids():
    pids = [2841291896, 2850103315]
    return {pid: get_field_in_pages(pid, 'html') for pid in pids}

def _same_length(count_A, count_B):
    print(f"{abs(count_A - count_B)} <? {0.02 * min(count_A, count_B)}")
    return abs(count_A - count_B) < 0.02 * min(count_A, count_B)
