# get helpful statistics out of your corpus
# -   stats authors
# -   stats links orphans
# -   stats links incoming PAGE_ID
# -   stats links popular
# -   stats links cross-space
# -   stats duplicates
# -   stats empty
# -   ...
from ccandle.config.config_app import FRIENDLY_APP_NAME
from ccandle.config.config_db import PATH_DB
from ccandle.spaces.space_utils import get_space_attribute, display_friendly_space_info
from ccandle.presentation.theme import *
from datetime import datetime, timedelta


def _add_common_args(sub):
    # args shared by every stats subcommand.
    sub.add_argument("--space-id", help="Limit search to only within a particular space")
    sub.add_argument("--limit", "-l", type=int, default=100, help="Limit to top L results")
    sub.add_argument("--db-path", default=PATH_DB, help=f"Get results from your specified database, instead of {FRIENDLY_APP_NAME}'s default")
    sub.add_argument("--ids-only", action="store_true", help="Print only IDs, one line, comma-separated")


def register(subparsers):
    p = subparsers.add_parser("stats", help="Learn statistics from your Confluence pages")
    stats_sub = p.add_subparsers(dest="stats_cmd")

    sub_authors = stats_sub.add_parser("authors", help="See top authors for your corpus")
    _add_common_args(sub_authors)

    # ——— LINKS STUFF ——————————————————————————————
    sub_links = stats_sub.add_parser("links", help="See info about the link distribution of your corpus")
    links_sub = sub_links.add_subparsers(dest="links_cmd")

    sub_orphans = links_sub.add_parser("orphans", help="Find pages with no incoming links")
    sub_popular = links_sub.add_parser("popular", help="See the most linked-to pages")
    sub_cross_space = links_sub.add_parser("cross-space", help="See links into/out of a space")
    sub_incoming = links_sub.add_parser("incoming", help="See what links to a specific page")
    sub_incoming.add_argument("page_id", help="Page ID to find incoming links for")     # extra positional arg

    links_subcommands = [sub_orphans, sub_popular, sub_cross_space, sub_incoming]
    for sub in links_subcommands:
        _add_common_args(sub)

    # ——— JUNK STUFF ———————————————————————————————
    sub_duplicates = stats_sub.add_parser("duplicates", help="Find likely duplicate pages")
    _add_common_args(sub_duplicates)
    sub_duplicates.add_argument("--fuzziness", type=float, default=1.0,
                                help="Finetune the threshold for considering pages as duplicates. E.g. 1.0 is default, 1.1 is less precise,...")

    sub_empty = stats_sub.add_parser("empty", help="Find pages in degrees of emptiness, to identify pages to delete or clean up")
    empty_sub = sub_empty.add_subparsers(dest="empty_cmd")

    sub_blanks = empty_sub.add_parser("blanks",       help="See truly blank pages. No words, no macros, empty html or at most some blank paragraph tags")
    sub_wordless = empty_sub.add_parser("wordless", help="See pages with zero word count. Often, these have a diagram or image, but don't deserve to be their own pages")
    sub_stubs = empty_sub.add_parser("stubs",         help="See stubs: short pages with very few words that would be better off incorporated into other pages")

    empty_subcommands = [sub_blanks, sub_wordless, sub_stubs]
    for sub in empty_subcommands:
        _add_common_args(sub)
        sub.add_argument("--min-age", type=int, default=0, help="Show only pages not edited in N days")
        sub.add_argument("--no-structural-value", "-nsv", action="store_true", help="Show only pages without a structural purpose, insufficient children, no links; the network and page tree won't notice if you kill it")

    # -- coming soon --
    sub_children = stats_sub.add_parser("children", help="See page hierarchy / child-count stats")
    _add_common_args(sub_children)


def run(args):
    from ccandle.presentation.page_previews import render_table
    from collections import Counter
    from ccandle.db.db_utils import get_all_ids_in_pages
    from ccandle.db.db_query_utils import query_field_multi_in_pages

    if args.stats_cmd == "authors":
        from ccandle.analysis.stats_authors import find_top_authors_across_pages

        COLUMNS = [
            {"key": "edits", "label": "EDITS", "width": 8},
            {"key": "name", "label": "AUTHOR", "width": 32},
        ]
        results = find_top_authors_across_pages(space_id=args.space_id, path_to_db=args.db_path, limit=args.limit)
        if args.ids_only:   print([res['name'] for res in results[:args.limit]])
        else:
            render_table(results, COLUMNS)
        return 0

    if args.stats_cmd == "links":
        from ccandle.analysis.stats_link_info import (find_orphaned_pages, find_max_linked_to_stats, find_incoming_links,
                                                          find_cross_space_links)
        if args.links_cmd == "orphans":
            print("Finding orphaned pages...")

            if args.space_id is not None:
                print(f"Filtering by your chosen space_id = {args.space_id}")
            else:
                print("Using all configured spaces, as you didn't specify a space to search within. "
                      "\nUse the flag --space-id SPACEID to specify a space next time.")

            results = find_orphaned_pages(space_id=args.space_id, path_to_db=args.db_path)
            print(f"\nTotal orphaned pages: {results['total']}\n")

            orphan_rows = results['detailed_rows']

            if args.ids_only:   print([orph[0] for orph in orphan_rows[:args.limit]])
            else:
                orphans_by_space = Counter(row[2] for row in orphan_rows)
                for space_id, orphans_in_space in sorted(orphans_by_space.items()):
                    total_in_space = len(get_all_ids_in_pages(space_id=space_id, path_to_db=args.db_path))
                    space_alias = get_space_attribute(space_id, "id", "alias").upper()
                    pct = 100 * orphans_in_space / total_in_space
                    print(f" {orphans_in_space:<5} /  {total_in_space:<5} = {pct:.0f}"
                          f" %  orphans in space {space_alias:<25} ({space_id})")

                COLUMNS = [
                    {"key": "id", "label": "PAGE ID", "width": 12},
                    {"key": "title", "label": "TITLE"},
                ]
                display_results = True
                if results['total'] > 200:
                    print(f"\nThere are {results['total']} orphaned pages. Do you really want to list them all? "
                          f"\nType 'yes' or 'no' to confirm.")
                    confirm = input().strip().lower()
                    if confirm not in ("yes", "y"):
                        display_results = False
                if display_results:
                    print(f"\nOrphaned pages ({len(orphan_rows)}):")
                    display_rows = [
                        {
                            "id": row[0],
                            "title": row[1],
                        }
                        for row in orphan_rows
                    ]
                    render_table(display_rows, COLUMNS)
                    return 0
            return 0

        # python cli.py stats links incoming PAGE
        if args.links_cmd == "incoming":
            results = find_incoming_links(pid=args.page_id, path_to_db=args.db_path)
            if args.ids_only:
                print(", ".join(r["linking_id"] for r in results[:args.limit]))
                return 0                    # exit immediately

            print(f"Analyzing incoming links for page ID {args.page_id}:\n")
            INCOMING_LINK_COLUMNS = [
                {"key": "linking_id", "label": "PAGE ID", "width": 12},
                {"key": "space_alias", "label": "FROM SPACE", "width": 22},
                {"key": "linking_title", "label": "TITLE"},
            ]
            render_table(results[:args.limit], INCOMING_LINK_COLUMNS)
            link_count = len(results)
            print(f"\nTotal: {link_count} link" + ("s." if link_count > 1 else "."))
            return 0

        # python cli.py stats links popular
        if args.links_cmd == "popular":
            results = find_max_linked_to_stats(space_id=args.space_id, path_to_db=args.db_path, limit=args.limit)

            if args.ids_only:
                print(", ".join(r["pid"] for r in results[:args.limit]))
                return 0                    # exit immediately

            print(f"\n{BLUE}Most 'popular' (most linked-to) pages in your tracked Confluence spaces."
                  f"\nThese are usually important pages, since the network of pages keep referring to them."
                  f"\nNote: {FRIENDLY_APP_NAME} can only search for incoming links from spaces you have configured."
                  f"\n{RESET}")

            COLUMNS = [
                {"key": "pid", "label": "PAGE ID", "width": 20},
                {"key": "space_alias", "label": "SPACE", "width": 20},
                {"key": "incoming_links", "label": "IN-LINKS", "width": 8},
                {"key": "title", "label": "TITLE"},
            ]
            render_table(results, COLUMNS)
            print("\a")
            return 0

        if args.links_cmd == "cross-space":
            if args.space_id is None:
                print(f"{RED}You must specify a space ID, to see which spaces it links to.{RESET}")
                return 1                        # exit immediately
            if not args.ids_only: print(f"{DIM}Analyzing links in space: {RESET}{display_friendly_space_info(args.space_id, color=True)}")
            self_link_count, cross_link_count, results = find_cross_space_links(
                input_space=args.space_id, path_to_db=args.db_path)
            if args.ids_only:
                print(", ".join(r["space_alias"] for r in results[:args.limit]))
                return 0                        # exit immediately

            total_linked_spaces = len(results) + (1 if self_link_count else 0)
            print(f"In total {BOLD}{total_linked_spaces}{RESET} spaces are linked to from this space.\n")

            if self_link_count:
                print(f"Internal (same-space) links: {BOLD}{self_link_count}{RESET}")

            print(f"Cross-space links: {BOLD}{cross_link_count}{RESET}\n")
            COLUMNS = [
                {"key": "space_id", "label": "SPACE ID", "width": 12},
                {"key": "space_alias", "label": "SHORT ID", "width": 19},
                {"key": "count", "label": "LINKS"},
            ]
            render_table(results[:args.limit], COLUMNS)
            return 0

    if args.stats_cmd == "duplicates":
        from ccandle.analysis.stats_duplicates import fetch_unique_duplicate_groups, scan_for_duplicates_in_corpus
        if args.fuzziness != 1.0:
            print(f"As you set fuzziness on the fly, we must re-calculate duplicates across your corpus.\n"
                  f"This may take a while, especially if you set a high fuzziness score...")
            dup_groups = scan_for_duplicates_in_corpus(args.fuzziness)
        else:
            dup_groups = fetch_unique_duplicate_groups(space_id=args.space_id)
        if args.ids_only:
            page_ids = [page_id
                for group in dup_groups
                for page_id in group]
            print(", ".join(page_ids[:args.limit]))
            return 0                  # exit immediately

        group_num = 1
        for dup_group in dup_groups:
            print(f"{DIM}" + "-" * WIDTH_NICE + f"{RESET}")
            print(f"{BOLD}Duplicate group {RED}{group_num}{RESET} {DIM}({len(dup_group)} members):{RESET}")
            for page_id in dup_group:
                title, space_id = query_field_multi_in_pages(page_id, "title", "space_id")
                space_alias = get_space_attribute(space_id, "id", "alias")
                print(f"{page_id:<12}  {DIM}|{RESET}  {space_alias:<20}  {DIM}|{RESET}  {title}")
            print()             # add a new line for visual break from next group
            group_num += 1

        total_pages = sum(len(group) for group in dup_groups)
        print(f"Found {RED}{len(dup_groups)}{RESET} duplicate groups containing {BOLD}{total_pages}{RESET} pages.")
        return 0

    if args.stats_cmd == "empty":
        from ccandle.analysis.stats_empty import find_blank_pages, find_stubs, find_wordless_pages, LANDING_PAGE_TYPES
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
            {"key": "title", "label": "TITLE"},
        ]
        results = []
        if args.empty_cmd == "blanks":
            results = find_blank_pages(space_id=args.space_id, path_to_db=args.db_path)
        elif args.empty_cmd == "wordless":
            results = find_wordless_pages(space_id=args.space_id, path_to_db=args.db_path)
        elif args.empty_cmd == "stubs":
            results = find_stubs(space_id=args.space_id, path_to_db=args.db_path)

        if args.no_structural_value:
            results = [res for res in results if res['landing_page_status'] == '-']
        if args.min_age != 0:
            results = [res for res in results if _stale_enough(res['last_modified'], args.min_age)]

        if args.ids_only:
            print([res['id'] for res in results[:args.limit]])
        else:
            print(f"{BLUE}{args.empty_cmd.upper()}{RESET}{DIM} pages have {explanations[args.empty_cmd]}{RESET}\n")
            print(f"{DIM}Legend of 'landing page' statuses:{RESET}")
            for label, desc in LANDING_PAGE_TYPES.items():
                print(f"   {label:<17}{DIM} :  {desc}{RESET}")
            print()

            render_table(results[:args.limit], COLUMNS)
            space_desc = f" across space {args.space_id}" if args.space_id else ""
            print(f"\n{DIM}There are {RESET}{BOLD}{len(results)}{RESET}{DIM} empty ({RESET}{BLUE}{args.empty_cmd.upper()}{RESET}{DIM}) pages in total{space_desc}.{RESET}")
            _print_total_and_limit_info(len(results), args.limit)
        return 0

    if args.stats_cmd == "children":
        print("stats children: not yet implemented")
        return 0

    return 1

def _print_total_and_limit_info(total, limit):
    print(f"{DIM}Showing ({RESET}{BOLD}{min(limit, total)} / {total}{RESET}{DIM}) results.\n"
          f"Use {RESET}{BLUE}--limit L{RESET}{DIM} to set how many results max to display{RESET}")

def _stale_enough(date_str, min_age_in_days):
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return datetime.utcnow() - dt >= timedelta(days=min_age_in_days)