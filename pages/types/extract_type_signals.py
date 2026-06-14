# extract page characteristic signals so we can distinguish what
# kind of page this smells like

from bs4 import BeautifulSoup
import re
from copy import copy
from config.confluence_auth import load_conf_url, fetch_conf_details
from pages.types.type_keyword_defs import TITLE_KEYWORD_LISTS, HEADERS_KEYWORD_LISTS, BODY_KEYWORD_LISTS
from pages.parsing.paragraph_parser import extract_prose_paragraphs
JIRA_URL = load_conf_url()+'browse/'
LINK_PREFIX = r'<a href="'
GITLAB_URL = "https://" + fetch_conf_details('repo_url')

# ——— DATES —————————————————————————————————————————————————
DATE_PATTERN = re.compile(r'(?<!\d)(?:\d{2}([\-./])\d{2}\1\d{4}|\d{4}([\-./])\d{2})(?=[\s\-_:.,;)]|$)')
BAD_DATE_PATTERN = re.compile(r'(?<!\w)(\d{4}([\-./])(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\2\d{2})(?=[\s\-_:.,;)]|$)')
REVERSE_DATE_PATTERN = re.compile(r'(?<!\d)(\d{2}([\-./])\d{2}\2\d{4})(?=[\s\-_:.,;)]|$)')

# detects date patterns in page titles — strong signal for meeting minutes and release notes
def date_pattern_in_title(page_title):
    return {
        'date': DATE_PATTERN.search(page_title) is not None,
        'date_bad': BAD_DATE_PATTERN.search(page_title) is not None,
        'date_reverse': REVERSE_DATE_PATTERN.search(page_title) is not None,
    }

# ——— TOPICAL KEY WORDS —————————————————————————————————————
# counts how many keywords from kw_list appear in text_snippet
def kw_in_text(text_snippet, kw_list):
    text = (text_snippet or "").lower()
    return sum(kw in text for kw in kw_list)

# aggregates keyword hit counts across title, headers, and body for all keyword lists
def kw_signals(title, soup, html, plain_text_body):
    signals = {}
    for key, kw_list in TITLE_KEYWORD_LISTS.items():
        signals[key] = kw_in_text(title, kw_list)
    headers = header_titles_from_soup(soup)
    for key, kw_list in HEADERS_KEYWORD_LISTS.items():
        signals[key] = kw_in_text(headers, kw_list)
    for key, kw_list in BODY_KEYWORD_LISTS.items():
        signals[key] = kw_in_text(plain_text_body, kw_list)
    return signals

# ——— TABLE SIGNALS —————————————————————————————————————————
# raw table count — a rough proxy for page structure density
def table_count_from_html(html):
    return len(re.findall(r"<table>", html))

# meeting minutes often allocate minute durations to agenda items inside tables
def table_minutes_text_count_from_soup(soup):
    duration_re = re.compile(r'\b([1-9]\d{0,2})\s*min\b', re.IGNORECASE)
    return sum(
        len(duration_re.findall(table.get_text(separator=' ', strip=True)))
        for table in soup.find_all('table')
    )

# word count outside tables — helps distinguish arch docs (dense tables) from minutes (sparse tables)
def table_word_count_outside_from_soup(soup):
    soup = copy(soup)
    for table in soup.find_all('table'):
        table.decompose()
    return word_count_from_soup(soup)

# five key table characteristics that fingerprint page type —
# arch pages have long, wordy cells; minutes have many short or empty ones
def table_cell_signature_stats_from_soup(soup):
    cell_word_counts = [
        len(cell.get_text(strip=True).split()) + len(cell.find_all('ri:user'))
        for cell in soup.find_all('td')
    ]
    cell_count = len(cell_word_counts)
    if cell_count > 0:
        # thresholds determined from population statistics on a corpus of ~6K pages
        return {
            "has_cells": True,
            "share_empty": sum(1 for c in cell_word_counts if c == 0) / cell_count,
            "share_short": sum(1 for c in cell_word_counts if c < 5) / cell_count,
            "has_long_cells": sum(1 for c in cell_word_counts if c > 100),
            "has_many_cells": cell_count > 40,
        }
    return {"has_cells": False, "share_empty": 0, "share_short": 0, "has_long_cells": False, "has_many_cells": False}

# images and diagrams outside tables — common in arch docs, rare in minutes
def table_diagram_and_image_counts_outside_from_soup(soup):
    soup = copy(soup)
    for table in soup.find_all("table"):
        table.decompose()
    html_without_tables = str(soup)
    return {
        "images": len(re.findall(r'</ac:image>', html_without_tables)),
        "diagrams": len(re.findall(r'<ac:structured-macro ac:name="drawio"', html_without_tables)),
    }
def image_count_from_html(html):
    return len(re.findall(r'</ac:image>', html))

# ——— MINOR FORMATTING ——————————————————————————————————————
# top level header count (h1/h2) — a proxy for document structure formality
def header_count_from_soup(soup):
    return len(soup.find_all(['h1', 'h2']))

# comma-joined h1/h2 text — used for header keyword matching in kw_signals
def header_titles_from_soup(soup):
    return ",".join(tag.get_text(strip=True) for tag in soup.find_all(['h1', 'h2']))

# paragraph length characteristics. Many lengthy paras suggests arch or canon docs
def paragraph_length_signals_from_soup(soup):
    SHORT_PARA, LONG_PARA = 30, 100
    paragraphs = extract_prose_paragraphs(soup)
    para_count = len(paragraphs)
    if para_count == 0:
        return {"count": 0, "longest": 0, "share_long": 0, "share_short": 0, "average": 0}
    return {
        "count": para_count,
        "longest": max(paragraphs),
        "share_long": sum(1 for p in paragraphs if p > LONG_PARA) / para_count,
        "share_short": sum(1 for p in paragraphs if p < SHORT_PARA) / para_count,
        "average": sum(p for p in paragraphs) / para_count,
    }

# bullet list count — high in canon/arch pages, low in minutes
def bullet_count_from_html(html):
    return len(re.findall(r"<ul>", html))

# ——— LINK SIGNALS ——————————————————————————————————————————
# raw confluence link count
def link_count_from_html(html):
    confluence_links = len(re.findall(r'<ac:link[>\s]', html))
    external_links   = len(re.findall(r'<a\s+[^>]*href=', html))
    return confluence_links + external_links

# jira links — strong indicator for release notes and performance test results
def link_jira_count_from_html(html):
    return (
        len(re.findall(LINK_PREFIX + JIRA_URL, html)) +
        len(re.findall(r'<ac:structured-macro ac:name="jira"', html))
    )

# gitlab links — technical pages reference repos; rare in minutes
def link_gitlab_count_from_html(html):
    print("DEBUG: Search target = " + LINK_PREFIX + GITLAB_URL)
    return len(re.findall(LINK_PREFIX + GITLAB_URL, html))

# ——— MACRO / STRUCTURE SIGNALS ————————————————————————————
# TOC macro count — arch and canon docs tend to have these; minutes rarely do
def macro_has_toc_from_html(html):
    return len(re.findall(r'<ac:structured-macro ac:name="toc"', html))

# jira query widget — typical of release notes and quality dashboards
def macro_has_jira_query_widget_from_html(html):
    return (
        html.find(load_conf_url() + "issues/?jql=project") != -1 and
        html.find("data-card-appearance=") != -1
    )

# count of @ mentions — lots of @s are a strong signal for meeting minutes
def macro_mentions_count_from_html(html):
    return len(re.findall(r'<ac:link><ri:user ri:account-id=', html))

# task items — common in workshop and meeting minutes pages
def macro_tasks_count_from_html(html):
    return len(re.findall(r'<ac:task>', html))

# standalone diagram count (outside tables) — useful for arch page detection
def diagram_count_from_html(html):
    return len(re.findall(r'<ac:structured-macro ac:name="drawio"', html))

# panels, expandables, and excerpts — give a sense of editorial structure and formality
def macro_structures_signals_from_html(html):
    panels = len(re.findall(r'<ac:structured-macro ac:name="panel"', html))
    expandables = len(re.findall(r'<ac:structured-macro ac:name="expand"', html))
    excerpts = len(re.findall(r'<ac:structured-macro ac:name="excerpt-include"', html))
    return {
        "total": panels + expandables + excerpts,
        "panels": panels,
        "expandables": expandables,
        "excerpts": excerpts,
    }

# ——— MICRO-FORMATTING SIGNALS ——————————————————————————————
def word_count_from_soup(soup):
    return len(soup.get_text(separator=' ', strip=True).split())

# low letter-to-digit ratio suggests data-heavy pages like perf test results
def digit_to_letter_ratio_from_text(plain_text):
    digit_count = sum(c.isdigit() for c in plain_text)
    letter_count = sum(c.isalpha() for c in plain_text)
    return letter_count / (digit_count + 1)

# scores a page title against a ruleset — kept here pending classifier refactor
def score_title_keywords(page_title, rules, debug_mode=False):
    title = page_title.lower()
    delta = 0
    for keywords, reward in rules:
        if any(kw in title for kw in keywords):
            delta += reward
            if debug_mode:
                print(f"DEBUG Title keyword match: {keywords} | reward / penalty: {reward}")
    return delta