# get basic stats on the link attributes of your corpus.
# - max linked to
# - orphans
# - incoming links for a page
# - cross space links

from ccandle.config.config_app import FRIENDLY_APP_NAME
from ccandle.config.config_db import PATH_DB
from ccandle.spaces.space_utils import get_space_attribute, get_space_id_fuzzy
from ccandle.db.db_utils import get_all_ids_in_pages, id_exists_in_table
from ccandle.db.db_query_utils import query_field_multi_in_pages, query_db_results
from collections import Counter
import re, json

SPACE_NAME_RE = re.compile(r"([A-Za-z0-9]+):")
LINK_ID_RE = re.compile(r":(\d+)(?:,|$)")

def find_max_linked_to_stats(space_id=None, path_to_db=PATH_DB, limit=20):
    all_ids = get_all_ids_in_pages(path_to_db=path_to_db)
    space_key = get_space_attribute(space_id, "id", "short_id") if space_id else None

    raw_links_total = []
    titles_by_pid = {}
    for pid in all_ids:
        link_count, links_list, title = query_field_multi_in_pages(
            pid, "link_count", "links_list", "title", path_to_db=path_to_db
        )
        titles_by_pid[str(pid)] = title

        if not links_list:
            continue
        links_list = json.loads(links_list)
        raw_links_total.extend(l.strip() for l in links_list if l and l.strip())

    links_and_counts = Counter(raw_links_total)

    if space_key:
        links_and_counts = Counter({
            link: count
            for link, count in links_and_counts.items()
            if link.upper().startswith(space_key.upper())
        })

    results = []
    for link, count in links_and_counts.most_common(limit):
        key, _, pid = link.partition(":")
        space_alias = get_space_attribute(key, "short_id", "alias") or key
        results.append({
            "space_alias": space_alias,
            "pid": pid,
            "incoming_links": count,
            "title": titles_by_pid.get(pid, pid),
        })
    return results

def _extract_link_ids(links_list) -> set[str]:
    """links_list: JSON-encoded string of 'SPACEKEY:pageid' link strings."""
    if not links_list:
        return set()
    parsed = json.loads(links_list)
    ids = set()
    for link in parsed:
        if not link:
            continue
        _, _, pid = link.partition(":")
        if pid:
            ids.add(pid.strip())
    return ids

def find_orphaned_pages(pids=None, space_id=None, path_to_db=PATH_DB):
    if pids is None:
        pids = set(get_all_ids_in_pages(space_id=space_id, path_to_db=path_to_db))
    else:
        pids = set(pids)

    incoming_links = set()
    rows = query_db_results(select_query="id, title, space_id, links_list", path_to_db=path_to_db)
    page_info = {str(row[0]): row[:3] for row in rows}  # id -> (id, title, space_id)

    for _, _, _, links_list in rows:
        incoming_links.update(_extract_link_ids(links_list))

    incoming_links_in_space = incoming_links & pids
    orphaned_pages = pids - incoming_links_in_space

    orphan_rows = [page_info[pid] for pid in orphaned_pages if pid in page_info]

    return {
        "detailed_rows": orphan_rows,
        "total": len(orphan_rows),
    }


# this could help for page archival / deletion flow: you can
# immediately tell which links to repair or watch out for.
def find_incoming_links(pid, path_to_db=PATH_DB):
    if not id_exists_in_table(pid):
        print(f"Page {pid} not found in your scraped Confluence spaces.\n"
              f"{FRIENDLY_APP_NAME} can't find data about a page you haven't scraped.")
        return 1

    rows = query_db_results(select_query="id, space_id, title",
                            where_clause=f"links_list LIKE '%{pid}%'",
                            path_to_db=path_to_db)
    results = [
        {
            "linking_id": row[0],
            "space_alias": get_space_attribute(row[1], "id", "alias"),
            "linking_title": row[2],
        }
        for row in rows
    ]
    return results

def _extract_space_names(links_list: str) -> list[str]:
    if not links_list:
        return []
    return SPACE_NAME_RE.findall(links_list)  # return all matches including duplicates

def find_cross_space_links(input_space, path_to_db=PATH_DB):
    # Resolve input space to canonical dict
    input_space = input_space.strip().upper()
    space_id = get_space_id_fuzzy(input_space)
    if space_id is None:
        raise ValueError(f"Unknown space identifier: {input_space}")

    space_short_id = get_space_attribute(space_id, "id", "short_id")

    # Query DB
    rows = query_db_results("links_list", where_clause= f"space_id={space_id}", path_to_db=path_to_db)
    all_links_lists = [row[0] for row in rows]

    space_counter = Counter()
    self_link_count = 0

    for links_list in all_links_lists:
        linked_spaces = _extract_space_names(links_list)
        for linked_space in linked_spaces:
            if linked_space == space_short_id:
                self_link_count += 1
            else:
                space_counter[linked_space] += 1

    cross_link_count = sum(space_counter.values())

    results = [{
            "space_id": get_space_attribute(linked_short_id, "short_id", "id") or '???',
            "space_alias": get_space_attribute(linked_short_id, "short_id", "alias") or linked_short_id,
            "count": count,
        }
        for linked_short_id, count in space_counter.most_common()]

    return self_link_count, cross_link_count, results
