from pages.parsing.excerpt_defs import NAVBOX_FLAG, EXCERPT_FLAG
from analysis.stats_link_info import find_orphaned_pages
from config.config_db import PATH_DB
from db.db_query_utils import query_db_results
from config.config_types import TYPE_ADMIN_FILTER
from pages.parsing.eval_defs import NOTES_LEAD_PARA_GOOD
from pages.types.type_signals_defs import THRESH_PAGE_EMPTY
from presentation.theme import *
from spaces.space_utils import list_configured_space_ids, get_space_attribute

STATS_KEYS = {
    # TOPOLOGY / CONNECTEDNESS
    "dead_ends_share": {
        "title": "Pages without links",
        "goal": 10.0,
        "group": "topology",
        "hint": "share of pages with no OUTgoing links",
    },
    "orphans_share": {
        "title": "Orphan pages",
        "goal": 40.0,
        "group": "topology",
        "hint": "share of pages with no INcoming links",
    },
    "link_density": {
        "title": "Link density",
        "goal": 3.0,
        "group": "topology",
        "hint": "links per 100 words across content pages",
    },
    # PAGE QUALITY
    "lead_paras_good_share": {
        "title": "Good lead paragraphs",
        "goal": 15.0,
        "group": "quality",
        'hint': "share of pages that have a descriptive leading paragraph with links",
    },
    "excerpts_and_reuse_share": {
        "title": "Pages reusing excerpts",
        "goal": 10.0,
        "group": "quality",
        "hint": "share pages reusing excerpts of other pages, reducing redundancy and drift",
    },
    "junk_pages_share": {
        "title": "Junk / empty pages",
        "goal": 5.0,
        "group": "quality",
        "hint": "share of pages that are empty, very short, or duplicated",
    },
    # NAVIGATION
    "landing_page_coverage": {
        "title": "Landing page coverage",
        "goal": 5.0,
        "group": "navigation",
        "hint": "",
    },
    "navbox_coverage": {
        "title": "Navbox coverage",
        "goal": 20.0,
        "group": "navigation",
        "hint": "share of pages containing navboxes, guiding users through a topic",
    },
    "hub_coverage": {
        "title": "Hub coverage",
         "goal": 20.0,
        "group": "navigation",
        "hint": "coverage of expected topic clusters with intro pages",
    },
}
STATS_GROUPS = ["topology", "quality", "navigation"]
STATS_GROUP_TITLES = {
    "topology": "TOPOLOGY / CONNECTEDNESS",
    "quality": "PAGE QUALITY",
    "navigation": "ADVANCED NAVIGATIONAL ELEMENTS",
}

def present_all_space_overviews(quiet=False, path_to_db=PATH_DB):
    space_ids = list_configured_space_ids()
    for space_id in space_ids:
        present_space_overview(space_id, quiet=quiet, path_to_db=path_to_db)

def present_space_overview(space_id, quiet=False, path_to_db=PATH_DB):
    space_alias = get_space_attribute(space_id, 'id', 'alias')
    space_shid = get_space_attribute(space_id, 'id', 'short_id')

    print('=' * WIDTH_NICE)
    print(f"{BOLD}OVERVIEW FOR SPACE {BLUE}{space_alias}{RESET} {DIM}({space_id}, {space_shid}){RESET}:")
    print()

    sdata = gather_relevant_space_data(space_id, path_to_db)
    print(f"Total pages in space" + " "*9 + f":{sdata['total_pages']:>9}")
    print(f"Total words in space" + " "*9 + f":{sdata['total_words']:>9}")
    print()
    print(f"Total content pages in space " + f":{sdata['content_pages']:>9}")
    print(f"Total words in content pages " + f":{sdata['content_words']:>9}")
    print()
    grouped_data = build_stat_view(sdata, quiet=quiet)
    print_grouped_stats(grouped_data)
    print("\n")

    print_page_types()

def gather_relevant_space_data(space_id=None, path_to_db=PATH_DB):
    space_query = f"space_id={space_id}" if space_id else "1=1"
    totals = query_db_results("COUNT(*), SUM(word_count)",
                      where_clause=space_query, path_to_db=path_to_db)[0]

    CF = f"{space_query} AND {TYPE_ADMIN_FILTER}"   # content pages filter
    content_totals = query_db_results("COUNT(*), SUM(word_count), SUM(link_count)",
                      where_clause=CF, path_to_db=path_to_db)[0]
    content_pages, content_words, content_links = content_totals[0], content_totals[1], content_totals[2]

    # connectedness
    dead_ends = query_db_results("COUNT(*)",
                     where_clause=f"{CF} AND link_count=0", path_to_db=path_to_db)[0][0]

    content_pids = [res[0] for res in query_db_results("id", where_clause=CF, path_to_db=path_to_db)]
    orphans = find_orphaned_pages(pids=content_pids, path_to_db=path_to_db)

    # page quality
    pages_w_good_lead_paras = query_db_results("COUNT(*)",
                     where_clause=f"{CF} AND eval_notes like '%{NOTES_LEAD_PARA_GOOD}%'", path_to_db=path_to_db)[0][0]
    pages_w_excerpts = query_db_results("COUNT(*)",
                     where_clause=f"{CF} AND excerpts like '%{EXCERPT_FLAG}:%'", path_to_db=path_to_db)[0][0]
    pages_w_duplicates = query_db_results("COUNT(*)",
                     where_clause=f"{CF} AND duplicate_list != '[]' AND duplicate_list is not null", path_to_db=path_to_db)[0][0]
    pages_empty = query_db_results("COUNT(*)",
                    where_clause=f"{CF} AND word_count < {THRESH_PAGE_EMPTY}", path_to_db=path_to_db)[0][0]

    # advanced nav elements
    pages_w_navboxes = query_db_results("COUNT(*)",
                    where_clause=f"{CF} AND excerpts like '%{NAVBOX_FLAG}:%'", path_to_db=path_to_db)[0][0]
    canonical_intros = query_db_results("COUNT(*)",
                    where_clause=f"{CF} AND page_type='canonical_intro'", path_to_db=path_to_db)[0][0]
    landing_pages = query_db_results("COUNT(*)",
                    where_clause=f"{CF} AND page_type='landing_page'", path_to_db=path_to_db)[0][0]


    return {
        'total_pages': totals[0],
        'total_words': totals[1],
        'content_pages': content_totals[0],
        'content_words': content_words,
        # connectedness
        'dead_ends_share': dead_ends / content_pages,
        'orphans_share': orphans['total'] / content_pages,
        'link_density': content_links / content_words,
        # page quality
        'lead_paras_good_share': pages_w_good_lead_paras / content_pages,
        'excerpts_and_reuse_share': pages_w_excerpts / content_pages,
        'junk_pages_share': (pages_w_duplicates + pages_empty) / content_pages,
        # advanced nav elements
        'landing_page_coverage': landing_pages / content_pages,
        'navbox_coverage': pages_w_navboxes / content_pages,
        'hub_coverage': canonical_intros / content_pages,
    }

def print_page_types(space_id):
    return 0



def build_stat_view(space_stats, quiet=False):
    grouped = {g: [] for g in STATS_GROUPS}

    for stat_name, value in space_stats.items():
        cfg = STATS_KEYS.get(stat_name)
        if not cfg:
            continue

        item = {
            "key": stat_name,
            "title": cfg["title"],
            "value": value,
            "goal": cfg.get("goal"),
            "hint": None if quiet else cfg.get("hint"),
        }

        grouped[cfg["group"]].append(item)

    return grouped

def print_grouped_stats(grouped_stats):
    for group in STATS_GROUPS:
        items = grouped_stats.get(group, [])
        if not items:
            continue

        print(f"\n{STATS_GROUP_TITLES[group]}")
        print("-" * WIDTH_NICE)

        for item in items:
            line = f"{item['title']:<27}: {(item['value'] * 100):5.1f} %"
            if item["goal"] is not None:
                line += f" | goal: {item['goal']:5.1f}"
            if item["hint"] is not None:
                line += f"  {DIM}→ {item['hint']}{RESET}"
            print(line)


