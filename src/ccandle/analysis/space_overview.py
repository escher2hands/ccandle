from ccandle.db.db_utils import get_all_ids_in_pages
from ccandle.pages.parsing.excerpt_defs import NAVBOX_FLAG, EXCERPT_FLAG
from ccandle.analysis.stats_link_info import find_orphaned_pages
from ccandle.config.config_db import PATH_DB
from ccandle.db.db_query_utils import query_db_results
from ccandle.config.config_types import TYPE_ADMIN_FILTER, TYPE_LIST
from ccandle.pages.parsing.eval_defs import NOTES_LEAD_PARA_GOOD
from ccandle.page_types.type_signals_defs import THRESH_PAGE_EMPTY
from ccandle.presentation.theme import *
from ccandle.spaces.space_utils import list_configured_space_ids, get_space_attribute, display_friendly_space_info
import sqlite3
from dataclasses import dataclass

@dataclass(frozen=True)
class StatConfig:
    title: str
    goal: float
    group: str
    hint: str = ""

STATS_KEYS = {
    # TOPOLOGY / CONNECTEDNESS
    "dead_ends_share": StatConfig(
        title="Pages without links",
        goal=10.0,
        group="topology",
        hint="share of pages with no OUTgoing links",
    ),
    "orphans_share": StatConfig(
        title="Orphan pages",
        goal=40.0,
        group="topology",
        hint="share of pages with no INcoming links",
    ),
    "link_density": StatConfig(
        title="Link density",
        goal=3.0,
        group="topology",
        hint="links per 100 words across content pages",
    ),
    "lead_paras_good_share": StatConfig(
        title="Good lead paragraphs",
        goal=15.0,
        group="quality",
        hint="share of pages that have a descriptive leading paragraph with links",
    ),
    "excerpts_and_reuse_share": StatConfig(
        title="Pages reusing excerpts",
        goal=10.0,
        group="quality",
        hint="share pages reusing excerpts of other pages, reducing redundancy and drift",
    ),
    "junk_pages_share": StatConfig(
        title="Junk / empty pages",
        goal=5.0,
        group="quality",
        hint="share of pages that are empty, very short, or duplicated",
    ),
    "landing_page_coverage": StatConfig(
        title="Landing page coverage",
        goal=5.0,
        group="navigation",
    ),
    "navbox_coverage": StatConfig(
        title="Navbox coverage",
        goal=20.0,
        group="navigation",
        hint="share of pages containing navboxes, guiding users through a topic",
    ),
    "hub_coverage": StatConfig(
        title="Hub coverage",
        goal=20.0,
        group="navigation",
        hint="coverage of expected topic clusters with intro pages",
    ),
}

STATS_GROUPS = ["topology", "quality", "navigation"]
STATS_GROUP_TITLES = {
    "topology": "TOPOLOGY / CONNECTEDNESS",
    "quality": "PAGE QUALITY",
    "navigation": "ADVANCED NAVIGATIONAL ELEMENTS",
}

def present_all_space_overviews(quiet=False, path_to_db=PATH_DB, json_format=False):
    space_ids = list_configured_space_ids()
    if json_format:
        results = []
        for space_id in space_ids:
            sdata = present_space_overview(space_id, quiet=quiet, path_to_db=path_to_db, json_format=json_format)
            results.append(sdata)
        return results
    else:
        for space_id in space_ids:
            present_space_overview(space_id, quiet=quiet, path_to_db=path_to_db, json_format=json_format)

    return 0

def present_space_overview(space_id=None, quiet=False, path_to_db=PATH_DB, json_format=False):
    if json_format:
        sdata = gather_relevant_space_data(space_id, path_to_db)
        sdata = {
            'space_id': space_id,
            'space_short_id': get_space_attribute(space_id, "id", "short_id"),
            'space_alias': get_space_attribute(space_id, "id", "alias"),
            'stats': {k: round(v, 4) if isinstance(v, float) else v
                  for k, v in sdata.items()},
            'page_types': gather_page_types_breakdown(space_id, path_to_db),
        }
        return sdata

    space_info = display_friendly_space_info(space_id, color=True, long=True) if space_id else "ALL CONFIGURED SPACES"
    print(f'{BLUE}' + '=' * WIDTH_NICE + f'{RESET}')
    print(f"{BOLD}OVERVIEW FOR SPACE {RESET}{space_info}:")
    print()

    sdata = gather_relevant_space_data(space_id, path_to_db)
    print(f"Total pages in space" + " "*9 + f":{sdata['total_pages']:>9}")
    print(f"Total words in space" + " "*9 + f":{sdata['total_words']:>9}")
    print()
    print(f"Total content pages in space " + f":{sdata['content_pages']:>9}")
    print(f"Total words in content pages " + f":{sdata['content_words']:>9}")
    print()
    print_grouped_stats(sdata, quiet=quiet)
    print("")

    print_page_types(space_id=space_id, total_pages=sdata['total_pages'], print_heading=False, path_to_db=path_to_db)
    print("\n")

def gather_relevant_space_data(space_id=None, path_to_db=PATH_DB):
    space_query = f"space_id={space_id}" if space_id else "1=1"
    totals = query_db_results("COUNT(*), SUM(word_count)",
                      where_clause=space_query, path_to_db=path_to_db)[0]

    CF = f"{space_query} AND {TYPE_ADMIN_FILTER}"   # content pages filter
    content_totals = query_db_results("COUNT(*), SUM(word_count), SUM(link_count)",
                      where_clause=CF, path_to_db=path_to_db)[0]

    content_pids = [res[0] for res in query_db_results("id", where_clause=CF, path_to_db=path_to_db)]
    orphans = find_orphaned_pages(pids=content_pids, path_to_db=path_to_db)

    with sqlite3.connect(path_to_db) as conn:
        conn.row_factory = sqlite3.Row  # enables stats["content_pages"] etc.
        params = {
            "lead_flag": f"%{NOTES_LEAD_PARA_GOOD}%",
            "excerpt_flag": f"%{EXCERPT_FLAG}:%",
            "navbox_flag": f"%{NAVBOX_FLAG}:%",
            "empty_thresh": THRESH_PAGE_EMPTY,
        }
        cur = conn.cursor()
        cur.execute(f"""
            SELECT
                COUNT(*)                                                    AS content_pages,
                SUM(word_count)                                             AS content_words,
                SUM(link_count)                                             AS content_links,
                COUNT(*) FILTER (WHERE link_count = 0)                     AS dead_ends,
                COUNT(*) FILTER (WHERE eval_notes LIKE :lead_flag)         AS good_lead_paras,
                COUNT(*) FILTER (WHERE excerpts   LIKE :excerpt_flag)      AS excerpts_reused,
                COUNT(*) FILTER (WHERE excerpts   LIKE :navbox_flag)       AS navboxes,
                COUNT(*) FILTER (WHERE duplicate_list NOT IN ('[]', '')
                                   AND duplicate_list IS NOT NULL)         AS duplicates,
                COUNT(*) FILTER (WHERE word_count < :empty_thresh)         AS empty_pages,
                COUNT(*) FILTER (WHERE page_type = 'canonical_intro')      AS canonical_intros,
                COUNT(*) FILTER (WHERE page_type = 'landing_page')         AS landing_pages
            FROM pages
            WHERE {CF}
            """, params  # dict goes in directly, no wrapping tuple needed
                    )
        stats = cur.fetchone()  # fetchone() since it's a single aggregation row

    cp = stats["content_pages"]
    cw = stats["content_words"]

    return {
        "total_pages":              totals[0],
        "total_words":              totals[1],
        "content_pages":            cp,
        "content_words":            cw,
        # topology
        "dead_ends_share":          share(stats["dead_ends"], cp),
        "orphans_share":            share(orphans["total"], cp),
        "link_density":             share(stats["content_links"], cw),
        # quality
        "lead_paras_good_share":    share(stats["good_lead_paras"], cp),
        "excerpts_and_reuse_share": share(stats["excerpts_reused"], cp),
        "junk_pages_share":         share((stats["duplicates"] + stats["empty_pages"]), cp),
        # navigation
        "landing_page_coverage":    share(stats["landing_pages"], cp),
        "navbox_coverage":          share(stats["navboxes"], cp),
        "hub_coverage":             share(stats["canonical_intros"], cp),
    }

def print_page_types(space_id, total_pages=None, print_heading=True, path_to_db=PATH_DB):
    type_stats = gather_page_types_breakdown(space_id, path_to_db)
    total_pages = total_pages or len(get_all_ids_in_pages(space_id=space_id))
    if print_heading:
        space_alias = get_space_attribute(space_id, 'id', 'alias')
        space_shid = get_space_attribute(space_id, 'id', 'short_id')
        print(f"{BOLD} OVERVIEW FOR SPACE {BLUE}{space_alias}{RESET} {DIM}({space_id}, {space_shid}){RESET}:")
    else:
        print(f"PAGE TYPE BREAKDOWN")
    print("-" * WIDTH_NICE)

    for p_type, count in type_stats.items():
        t_share = share(count, total_pages) * 100
        print(f"{t_share:2.0f} %    ({count:5} pages)    {p_type}")

def gather_page_types_breakdown(space_id, path_to_db):
    space_query = f"space_id={space_id}" if space_id else "1=1"
    SF = f"{space_query}"   # don't filter for types here, as we want the full breakdown
    with sqlite3.connect(path_to_db) as conn:
        conn.row_factory = sqlite3.Row

        # Build one SELECT line per type, using positional ? params
        select_lines = ",\n            ".join(
            f"COUNT(*) FILTER (WHERE page_type = ?) AS {p_type}"
            for p_type in TYPE_LIST
        )
        params = tuple(TYPE_LIST)

        cur = conn.cursor()
        cur.execute(f"""
            SELECT
                {select_lines}
            FROM pages
            WHERE {SF}
            """, params
                    )
        row = cur.fetchone()

    return {p_type: row[p_type] for p_type in TYPE_LIST}

def print_grouped_stats(space_stats, quiet=False):
    for group in STATS_GROUPS:
        items = [(key, cfg) for key, cfg in STATS_KEYS.items() if cfg.group == group]
        if not items:
            continue

        print(f"\n{STATS_GROUP_TITLES[group]}")
        print("-" * WIDTH_NICE)

        for key, cfg in items:
            value = space_stats.get(key)
            if value is None:
                continue
            line = f"{cfg.title:<27}: {(value * 100):5.1f} %"
            if cfg.goal is not None:
                line += f" | goal: {cfg.goal:5.1f}"
            if not quiet and cfg.hint:
                line += f"  {DIM}→ {cfg.hint}{RESET}"
            print(line)

def share(numerator, denominator):
    return numerator / denominator if denominator else 0.0
