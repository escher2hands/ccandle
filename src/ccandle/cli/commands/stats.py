# get helpful statistics out of your corpus
# -   stats authors
# -   stats links orphans
# -   stats links incoming PAGE_ID
# -   stats links popular
# -   stats links cross-space
# -   stats duplicates
# -   stats empty
# -   ...
from ccandle.config.config_app import FRIENDLY_APP_NAME, APP_HANDLE
from ccandle.config.config_db import PATH_DB
from ccandle.presentation.theme import *
from ccandle.presentation.user_communication import emit_results, fetch_with_spinner
from datetime import datetime, timedelta


def register(subparsers):
    p = subparsers.add_parser("stats",                  help="Learn deeper statistics from your Confluence pages")
    stats_sub = p.add_subparsers(dest="stats_cmd",      required=True)

    sub_authors = stats_sub.add_parser("authors",       help="See top authors for your corpus")
    _add_common_args(sub_authors)

    # ——— LINKS STUFF ——————————————————————————————
    sub_links = stats_sub.add_parser("links",           help="See deep info about the link distribution and connectedness of your corpus")
    links_sub = sub_links.add_subparsers(dest="links_cmd", required=True)

    sub_orphans = links_sub.add_parser("orphans",       help="Find pages with no incoming links, and see their distribution by space")
    orphan_type = sub_orphans.add_subparsers(dest="orph_cmd", required=False)
    sub_orphans.set_defaults(orph_cmd="breakdown")  # default when no sub-subcommand given
    orphans_breakdown = orphan_type.add_parser("breakdown", help="Analyze share of orphan pages per space")
    _add_common_args(orphans_breakdown)
    orphans_list = orphan_type.add_parser("list", help="List out your orphan pages")
    _add_common_args(orphans_list)

    sub_popular = links_sub.add_parser("popular",       help="See the most linked-to pages")
    sub_cross_space = links_sub.add_parser("cross-space", help="See links into/out of a space")
    sub_incoming = links_sub.add_parser("incoming",     help="See what links to a specific page")
    sub_incoming.add_argument("page_id",                help="Page ID to find incoming links for")     # extra positional arg

    links_subcommands = [sub_orphans, sub_popular, sub_cross_space, sub_incoming]
    for sub in links_subcommands:
        _add_common_args(sub)

    # ——— JUNK STUFF ———————————————————————————————
    sub_duplicates = stats_sub.add_parser("duplicates", help="Find likely duplicate pages")
    _add_common_args(sub_duplicates)
    sub_duplicates.add_argument("--fuzziness", type=float, default=1.0,
                                                        help="Finetune the threshold for considering pages as duplicates. E.g. 1.0 is default, 1.1 is less precise,...")

    sub_empty = stats_sub.add_parser("empty",           help="Find pages in degrees of emptiness, to identify pages to delete or clean up")
    empty_sub = sub_empty.add_subparsers(dest="empty_cmd", required=True)

    sub_blanks = empty_sub.add_parser("blanks",         help="See truly blank pages: no words, no macros, empty html or at most some blank paragraph tags")
    sub_wordless = empty_sub.add_parser("wordless",     help="See pages with zero word count: often, these have a diagram or image, but don't deserve to be their own pages")
    sub_stubs = empty_sub.add_parser("stubs",           help="See stubs: short pages with very few words that would be better off incorporated into other pages")

    empty_subcommands = [sub_blanks, sub_wordless, sub_stubs]
    for sub in empty_subcommands:
        _add_common_args(sub)
        sub.add_argument("--min-age", type=int, default=0, help="Show only pages not edited in N days")
        sub.add_argument("--no-structural-value", "-nsv", action="store_true", help="Show only pages without a structural purpose, insufficient children, no links; the network and page tree won't notice if you kill it")
        sub.add_argument("--clickable", action="store_true", help="Include clickable links for each result")

    # ——— CHILD STUFF ———————————————————————————————
    sub_children = stats_sub.add_parser("children",     help="See direct children and deep descendants of a specified page")
    sub_children.add_argument("page_id",                help="The page to find descendants of")
    sub_children.add_argument("--max-depth", type=int,  help="Show only page descendants up to a specified depth")
    _add_common_args(sub_children)

def _add_common_args(sub):
    # args shared by every stats subcommand.
    sub.add_argument("--space",                         help="Limit search to only within a particular space")
    sub.add_argument("--limit", "-l", type=int, default=100, help="Limit to top L results")
    sub.add_argument("--db-path", default=PATH_DB,      help=f"Get results from your specified database, instead of {FRIENDLY_APP_NAME}'s default")
    sub.add_argument("--ids", action="store_true", help="Output only IDs, in-line, comma-separated")
    sub.add_argument("--json", action="store_true", help="Output in machine-parseable JSON format")

def run(args):
    from ccandle.presentation.user_communication import clean_user_space_id_or_exit

    space_id = clean_user_space_id_or_exit(args.space)       # clean our space identifier input, and exit if invalid
    machine_format = args.ids or args.json

    if args.stats_cmd == "authors":
        return _run_authors(args, space_id, machine_format)
    elif args.stats_cmd == "links":
        if args.links_cmd == "orphans":
            return _run_links_orphans(args, space_id, machine_format)
        # ccandle stats links incoming PAGE
        elif args.links_cmd == "incoming":
            return _run_links_incoming(args, space_id, machine_format)
        # ccandle stats links popular
        elif args.links_cmd == "popular":
            return _run_links_popular(args, space_id, machine_format)
        # ccandle stats links cross-space --space SPACE
        elif args.links_cmd == "cross-space":
            return _run_links_cross_space(args, space_id, machine_format)

    # ccandle stats duplicates
    elif args.stats_cmd == "duplicates":
        return _run_duplicates(args, space_id, machine_format)

    elif args.stats_cmd == "empty":
        return _run_empty(args, space_id, machine_format)

    elif args.stats_cmd == "children":
        return _run_children(args, space_id, machine_format)
    return 0

# ------ individual runs ------------------------
def _run_authors(args, space_id, machine_format):
    from ccandle.analysis.stats_authors import find_top_authors_across_pages

    if not machine_format:
        print(f"{BLUE}Note that author edit history is compressed. \n"
             f"{DIM}strings of long back-to-back edits are capped at 3. \n"
             f"So {RESET}{DIM}[A A A A B B C A B B B B B]{BLUE} is compressed to {RESET}{DIM}[A A A B B C A B B B]{BLUE}\n"
             f"This unskews results from explosive edit bursts per author.{RESET}\n")

    COLUMNS = [
        {"key": "name", "label": "AUTHOR", "width": 32},
        {"key": "edits", "label": "# EDITS"},
        {"key": "pages", "label": "UNIQUE PAGES EDITED"},
    ]
    info = find_top_authors_across_pages(space_id=space_id, path_to_db=args.db_path, limit=args.limit)
    emit_results(info['results'], COLUMNS, args, id_key="name", your_total=info['unique_authors'])
    return 0

def _run_links_orphans(args, space_id, machine_format):
    from ccandle.analysis.stats_link_info import find_orphaned_pages
    from ccandle.db.db_utils import get_all_ids_in_pages
    from ccandle.spaces.space_utils import get_space_attribute
    from collections import Counter

    results = fetch_with_spinner(find_orphaned_pages, machine_format, f"{DIM}Finding orphaned pages...{RESET}",
                                  space_id=space_id, path_to_db=args.db_path)
    orphan_rows = results['detailed_rows']

    if args.orph_cmd == "breakdown":
        orphans_by_space = Counter(row[2] for row in orphan_rows)

        breakdown = []
        for sid, orphans_in_space in sorted(orphans_by_space.items()):
            total_in_space = len(get_all_ids_in_pages(space_id=sid, path_to_db=args.db_path))
            breakdown.append({
                "space_id": sid,
                "space_alias": get_space_attribute(sid, "id", "alias").upper(),
                "space_shid": get_space_attribute(sid, "id", "short_id").upper(),
                "orphans": orphans_in_space,
                "total": total_in_space,
                "share": round(orphans_in_space / total_in_space, 4),
            })
        COLUMNS = [
            {"key": "space_id", "label": "SPACE ID", "width": 12},
            {"key": "space_shid", "label": "SPACE SHORT ID"},
            {"key": "space_alias", "label": "SPACE NAME", "width": 25},
            {"key": "orphans", "label": "ORPHANS"},
            {"key": "total", "label": "OF TOTAL"},
        ]
        if not machine_format:
            for br in breakdown:
                br['percent'] = f"{round(100 * br['orphans'] / br['total'], 2)} %"
            COLUMNS.append({"key": "percent", "label": "SHARE"})
        else:
            COLUMNS.append({"key": "share", "label": "SHARE"})

        emit_results(breakdown, COLUMNS, args, id_key="space_shid")
        if not machine_format:
            print(f"\n{DIM}Run {RESET}\n"
                  f"   {APP_HANDLE} stats links orphans list\n"
                  f"{DIM}to list all {results['total']} orphaned pages\n"
                  f"Use {BLUE}--limit L{RESET}{DIM} or {BLUE}--space SPACE{RESET}{DIM} to restrict results.{RESET}")
        return 0

    elif args.orph_cmd == "list":
        COLUMNS = [
            {"key": "id", "label": "PAGE ID", "width": 12},
            {"key": "space_shid", "label": "SPACE"},
            {"key": "page_type", "label": "PAGE TYPE"},
            {"key": "title", "label": "TITLE"},
        ]
        display_rows = [
            {
                "id": row[0],
                "space_shid": get_space_attribute(row[2], 'id', 'short_id'),
                "page_type": row[3],
                "title": row[1],
            }
            for row in orphan_rows
        ]

        emit_results(display_rows, COLUMNS, args, id_key="id")
    return 0

def _run_links_incoming(args, space_id, machine_format):
    from ccandle.analysis.stats_link_info import find_incoming_links
    results = find_incoming_links(pid=args.page_id, space_id=space_id, path_to_db=args.db_path)

    COLUMNS = [
        {"key": "linking_id", "label": "PAGE ID", "width": 12},
        {"key": "space_shid", "label": "FROM SPACE"},
        {"key": "count_incoming", "label": "# IN LINKS"},
        {"key": "linking_title", "label": "TITLE"},
    ]

    emit_results(results, COLUMNS, args, id_key="linking_id")
    return 0

def _run_links_popular(args, space_id, machine_format):
    from ccandle.analysis.stats_link_info import find_max_linked_to_stats
    from ccandle.db.db_utils import get_all_ids_in_pages

    if not machine_format:
        print(f"{BLUE}Most 'popular' (most linked-to) pages in your tracked Confluence spaces.\n"
              f"{DIM}These are usually important pages, since your network of pages keep referring to them.\n"
              f"Note: {FRIENDLY_APP_NAME} can only find incoming links from spaces you have configured.\n{RESET}")
    results = fetch_with_spinner(find_max_linked_to_stats, machine_format, f"{DIM}Finding the most popular pages across your corpus...",
                                  space_id=space_id, path_to_db=args.db_path, limit=args.limit)

    COLUMNS = [
        {"key": "pid", "label": "PAGE ID", "width": 20},
        {"key": "space_shid", "label": "SPACE"},
        {"key": "incoming_links", "label": "IN-LINKS", "width": 8},
        {"key": "title", "label": "TITLE"},
    ]

    total = len(get_all_ids_in_pages(space_id=space_id, path_to_db=args.db_path))
    emit_results(results, COLUMNS, args, id_key="pid", your_total=total)
    return 0


def _run_links_cross_space(args, space_id, machine_format):
    from ccandle.analysis.stats_link_info import find_cross_space_links
    from ccandle.spaces.space_utils import display_friendly_space_info

    if space_id is None:
        print(f"{RED}You must specify a space ID, to see which spaces it links to.{RESET}")
        return 1  # exit immediately
    if not machine_format: print(
        f"{DIM}Analyzing links in space: {RESET}{display_friendly_space_info(space_id, color=True)}")
    self_link_count, cross_link_count, results = find_cross_space_links(input_space=space_id, path_to_db=args.db_path)
    total_linked_spaces = len(results) + (1 if self_link_count else 0)
    COLUMNS = [
        {"key": "space_id", "label": "SPACE ID"},
        {"key": "space_short_id", "label": "SHORT SPACE ID"},
        {"key": "space_alias", "label": "ALIAS"},
        {"key": "count", "label": "LINKS"},
    ]

    if not machine_format:
        print(
            f"{DIM}In total {RESET}{BOLD}{total_linked_spaces}{RESET}{DIM} spaces are linked to from this space.{RESET}\n")
        print(f"Internal (same-space) links: {BOLD}{self_link_count}{RESET}")
        print(f"Cross-space links: {BOLD}{cross_link_count}{RESET}\n")

    emit_results(results, COLUMNS, args, id_key="space_short_id")
    return 0

def _run_duplicates(args, space_id, machine_format):
    from ccandle.analysis.stats_duplicates import fetch_unique_duplicate_groups, scan_for_duplicates_in_corpus
    from ccandle.db.db_query_utils import query_field_multi_in_pages
    from ccandle.spaces.space_utils import get_space_attribute
    from ccandle.spaces.space_utils import display_friendly_space_info
    import json

    if args.fuzziness != 1.0:
        if not machine_format:
            print(f"As you set fuzziness on the fly, we must re-calculate duplicates across your corpus.\n"
                  f"This may take a while, especially if you set a high fuzziness score...")
        dup_groups = fetch_with_spinner(scan_for_duplicates_in_corpus, machine_format, f"{DIM}Finding duplicates across your corpus...",
                                  fuzziness=args.fuzziness, path_to_db=args.db_path)
    else:
        dup_groups = fetch_with_spinner(fetch_unique_duplicate_groups, machine_format, f"{DIM}Finding duplicates across your corpus...",
                                  space_id=space_id, path_to_db=args.db_path)
    if args.ids:
        pids = [pid for group in dup_groups[:args.limit] for pid in group]
        print(", ".join(pids))
        return 0  # exit immediately

    group_num = 1
    if args.json:
        output = []
        for group_num, dup_group in enumerate(dup_groups[:args.limit], start=1):
            members = []
            for page_id in dup_group:
                title, sid = query_field_multi_in_pages(page_id, "title", "space_id")
                members.append({
                    "pid": page_id,
                    "space_id": sid,
                    "space": get_space_attribute(sid, "id", "short_id"),
                    "title": title,
                })
            output.append({"group": group_num, "members": members, })
        print(json.dumps(output[:args.limit], indent=2))
    else:
        for dup_group in dup_groups[:args.limit]:
            print(f"{DIM}" + "-" * WIDTH_NICE + f"{RESET}")
            print(f"{BOLD}Duplicate group {RED}{group_num}{RESET} {DIM}({len(dup_group)} members):{RESET}")
            for page_id in dup_group:
                title, sid = query_field_multi_in_pages(page_id, "title", "space_id")
                space_string = display_friendly_space_info(sid, color=False)
                print(f"{page_id:<12}  {DIM}|{RESET}  {space_string:<20}  {DIM}|{RESET}  {title}")
            print()  # add a new line for visual break from next group
            group_num += 1

        total_pages = sum(len(group) for group in dup_groups)
        print(f"Found {RED}{len(dup_groups)}{RESET} duplicate groups containing {BOLD}{total_pages}{RESET} pages.")
    return 0

def _run_empty(args, space_id, machine_format):
    from ccandle.analysis.stats_empty import find_blank_pages, find_stubs, find_wordless_pages, STRUCTURAL_TYPES
    explanations = {
        "blanks": "zero content, zero words — safe to directly delete",
        "wordless": "zero words, but with image/diagram/codeblock — extract asset and roll up into another page (maybe its parent?)",
        "stubs": "some words, but don't deserve to stand on their own as a page — roll up into another page (maybe its parent?) and edit to fit",
    }
    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "space_shid", "label": "SPACE", "width": 10},
        {"key": "word_count", "label": "# WORDS", "width": 7},
        {"key": "last_modified", "label": "LAST MODIFIED", "width": 13},
        {"key": "landing_page_status", "label": "STRUCTURAL VAL?", "width": 15},
        {"key": "title", "label": "TITLE", "width": 50},
    ]
    if not machine_format:
        print(f"{BLUE}{args.empty_cmd.upper()}{DIM} pages have {explanations[args.empty_cmd]}{RESET}\n")
        print(f"{DIM}Legend of 'structural value' statuses:{RESET}")
        for label, desc in STRUCTURAL_TYPES.items():
            print(f"   {label:<17}{DIM} :  {desc}{RESET}")
        print()

    results = []
    if args.empty_cmd == "blanks":
        results = fetch_with_spinner(find_blank_pages, machine_format, f"{DIM}Finding blank pages...",
                                  space_id=space_id, path_to_db=args.db_path)
    elif args.empty_cmd == "wordless":
        results = fetch_with_spinner(find_wordless_pages, machine_format, f"{DIM}Finding wordless pages...",
                                  space_id=space_id, path_to_db=args.db_path)
    elif args.empty_cmd == "stubs":
        results = fetch_with_spinner(find_stubs, machine_format, f"{DIM}Finding stub pages...",
                                  space_id=space_id, path_to_db=args.db_path)

    if args.no_structural_value:
        results = [res for res in results if res['landing_page_status'] == '-']
    if args.min_age != 0:
        results = [res for res in results if _stale_enough(res['last_modified'], args.min_age)]

    if args.clickable:
        COLUMNS.append({"key": "tiny_link", "label": "LINK"})

    emit_results(results, COLUMNS, args, id_key="id")
    return 0

def _run_children(args, space_id, machine_format):
    from ccandle.analysis.stats_cartography import get_descendants
    from ccandle.db.db_utils import get_field_in_pages
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db

    exit_if_not_all_ids_are_in_db([args.page_id])

    if space_id is None:
        space_id = get_field_in_pages(args.page_id, 'space_id')
    results = get_descendants(space_id=space_id, page_id=args.page_id, path_to_db=args.db_path)
    if args.max_depth is not None:
        results = [res for res in results if res['depth'] <= args.max_depth]

    COLUMNS = [
        {"key": "pid", "label": "PAGE ID", "width": 11},
        {"key": "depth", "label": "DEPTH", "width": 6},
        {"key": "title", "label": "TITLE"},
    ]
    emit_results(results, COLUMNS, args, id_key="pid")
    return 0

# ------ helpers --------------------------------
def _stale_enough(date_str, min_age_in_days):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return datetime.utcnow() - dt >= timedelta(days=min_age_in_days)
