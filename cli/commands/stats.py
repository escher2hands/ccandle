# get helpful statistics out of your corpus
# -   stats authors
# -   ...



def register(subparsers):
    p = subparsers.add_parser("stats", help="Learn statistics from your Confluence pages")
    stats_sub = p.add_subparsers(dest="stats_cmd")

    sub = stats_sub.add_parser("authors", help="See top authors for your corpus")
    sub.add_argument("--space-id", help="Limit search to only within a particular space")
    sub.add_argument("--limit", "-l", type=int, default=50, help="Limit to top N results")

def run(args):
    from space_stats.stats_authors import find_top_authors_across_pages
    from presentation.page_previews import render_table

    COLUMNS = [
        {"key": "edits", "label": "EDITS", "width": 8},
        {"key": "name", "label": "AUTHOR", "width": 32},
    ]
    results = find_top_authors_across_pages(space_id=args.space_id, limit=args.limit)
    render_table(results, COLUMNS)
    return 0