from ccandle.analysis.stats_excerpts import deserialize_excerpt
from ccandle.db.db_query_utils import query_field_multi_in_pages
from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db
from ccandle.presentation.theme import *
from ccandle.config.config_db import PATH_DB
from ccandle.config.config_app import FRIENDLY_APP_NAME
import json

def register(subparsers):
    p = subparsers.add_parser("excerpts", help="Manage excerpts in bulk: list all in your local pages, find excerpt sources, and add / remove navboxes to pages by id list")
    excerpts_sub = p.add_subparsers(dest="excerpts_cmd")

    # so many arguments!
    sub_list = excerpts_sub.add_parser("list", help="List all excerpts in your corpus")
    sub_list.add_argument("--sources-only", "-s", action="store_true", help="Show only sources")
    sub_list.add_argument("--navboxes-only", "-n", action="store_true", help="Show only navboxes")
    sub_list.add_argument("--space-id", help="Limit search to only within a particular space")
    sub_list.add_argument("--limit", "-l", type=int, default=50, help="Limit to top N results")
    sub_list.add_argument("--db-path", default=PATH_DB, help=f"Get results from your specified database, instead of {FRIENDLY_APP_NAME}'s default")
    sub_list.add_argument("--ids-only", action="store_true", help="Print only IDs, one line, comma-separated")

    for name, help_text in [
        ("add",        "Add specified excerpt (using its source page ID) to the list of page IDs"),
        ("remove",     "Delete specified excerpt (using its source page ID) from the list of page IDs"),
    ]:
        sub = excerpts_sub.add_parser(name, help=help_text)
        sub.add_argument("excerpt_source_id", help="The page to take an excerpt from")
        sub.add_argument("page_ids", nargs="+", help="List of pages by id to apply the excerpt change to")



def run(args):
    from ccandle.excerpts.excerpt_bulk_actions import remove_excerpts_from_pages_in_bulk, insert_excerpts_to_pages_in_bulk, extract_excerpt_data
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.formatting_utils import parse_pids_from_terminal
    from ccandle.presentation.page_previews import render_table
    from ccandle.presentation.user_communication import get_confirmation_to_continue

    if not check_network_connection():
        return 1

    COLUMNS = [
        {"key": "id", "label": "PAGE ID", "width": 11},
        {"key": "excerpt_names", "label": "EXISTING EXCERPTS", "width": 50},
        {"key": "version", "label": "VERS", "width": 5},
        {"key": "title", "label": "TITLE"},
    ]

    ops = {
        "add": ("add", "to", insert_excerpts_to_pages_in_bulk),
        "remove": ("remove", "from", remove_excerpts_from_pages_in_bulk),
    }
    if args.excerpts_cmd in ops:
        operation, preposition, fn = ops[args.excerpts_cmd]

        pids = parse_pids_from_terminal(args.page_ids)
        exit_if_not_all_ids_are_in_db(pids, source_pid=args.excerpt_source_id)  # ensure all are valid pids in our local
        excerpt_source_data = extract_excerpt_data(args.excerpt_source_id)
        print(f"Are you sure you'd like to {operation} the excerpt: \n"
              f"- '{BLUE}{excerpt_source_data['name']}{RESET}' from page '{BLUE}{excerpt_source_data['title']}{RESET}'\n"
              f"{preposition} the following {BOLD}{len(pids)}{RESET} pages?\n")

        results = _get_preview_of_pages(pids)
        render_table(results, COLUMNS)
        get_confirmation_to_continue()
        failures = []
        if args.excerpts_cmd == "add":
            failures = insert_excerpts_to_pages_in_bulk(args.excerpt_source_id, pids)
        elif args.excerpts_cmd == "remove":
            failures = remove_excerpts_from_pages_in_bulk(pids)
        if failures:
            print(f"\nSome of your excerpt operations weren't successful:\n")
            for failure in failures:
                vers = f"| vers: {failure['version']}" if failure['status'] == 'error' else ""
                http_status = f"| http status: {failure['http_status']}" if failure['status'] == 'error' else ""
                print(f"{RED}-   {failure['id']} | {failure['status']}{vers}{http_status}{RESET}")
            print(f"\nPlease double check these manually.")
        print("\nResults:\n")
        new_results = _get_preview_of_pages(pids)
        render_table(new_results, COLUMNS)
        return 0

    # TODO: update the excerpts commands for listing and finding. Probably should add
    #  filtering for source vs consumer, mentions of specific excerpt
    if args.excerpts_cmd == "list":
        from ccandle.db.db_query_utils import query_db_results
        from ccandle.analysis.stats_excerpts import deserialize_excerpt
        from ccandle.spaces.space_utils import get_space_attribute
        import json
        space_query = f"space_id={args.space_id}" if args.space_id else "1=1"
        excerpts_filter = "excerpts is not null"
        select_query = "id, space_id, title, excerpts"
        path_db = args.db_path if args.db_path else PATH_DB
        results = query_db_results(select_query, where_clause=f"{space_query} AND {excerpts_filter}", path_to_db=path_db)

        excerpt_data = []
        for res in results:
            space_shid = get_space_attribute(res[1], "id", "short_id")
            serialized_excerpts = json.loads(res[3])
            for ser_excerpt in serialized_excerpts:
                deser_excerpt = deserialize_excerpt(ser_excerpt)
                excerpt = {
                    'id': res[0],
                    'space_alias': space_shid,
                    'excerpt_type': deser_excerpt["type"],
                    'excerpt_name': deser_excerpt["name"],
                    'excerpt_is_source': deser_excerpt["is_source"],
                    'excerpt_source': deser_excerpt["source_id"],
                    'title': res[2],
                }
                if args.sources_only and deser_excerpt['is_source'] != 'source':
                    continue
                if args.navboxes_only and deser_excerpt['type'] != 'navbox':
                    continue
                excerpt_data.append(excerpt)

        COLUMNS = [
            {"key": "id", "label": "PAGE ID", "width": 12},
            {"key": "space_alias", "label": "SPACE", "width": 9},
            {"key": "excerpt_name", "label": "EXCERPT NAME", "width": 25},
            {"key": "excerpt_type", "label": "EXC. TYPE", "width": 9},
            {"key": "excerpt_source", "label": "EXC. SOURCE", "width": 12},
            {"key": "title", "label": "PAGE TITLE"},
        ]
        render_table(excerpt_data[:args.limit], COLUMNS)
        print(f"\n{DIM}There are {RESET}{len(excerpt_data)}{DIM} excerpts in total. \n"
              f"Use {RESET}{BLUE} --limit L{RESET}{DIM} to set how many results to display.")

    return 1

def _get_preview_of_pages(pids):
    results = []
    for pid in pids:
        excerpt_data, version, title = query_field_multi_in_pages(pid, "excerpts", "version", "title")
        result = {
            "id": pid,
            "version": version,
            "excerpt_names": "",
            "title": title,
        }
        excerpt_data = json.loads(excerpt_data) if excerpt_data else {}
        for excerpt in excerpt_data:
            excerpt = deserialize_excerpt(excerpt)
            exc_string = f"{excerpt['name']}:{excerpt['type']}"
            result['excerpt_names'] += exc_string + " | "
        results.append(result)
    return results