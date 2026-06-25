from config.config_app import APP_HANDLE
from presentation.page_previews import render_table
from presentation.theme import *
from spaces.space_utils import get_space_attribute


def register(subparsers):
    p = subparsers.add_parser("cartography", help="Learn quick stats on your configured Confluence spaces")
    p.add_argument("--space-id", help="Narrow overview to just one space")
    p.add_argument("--quiet", "-q", action="store_true", default=False,
                        help="Mute verbose explanations")
    p.add_argument("--limit", "-l", type=int, default=25, help="Limit to top N results")

def run(args):
    from analysis.stats_cartography import make_maps
    if args.space_id is None:
        print(f"{RED}You must specify a space id.\n"
              f"{DIM}To map out structure and content distribution of a space, \n"
              f"specify the space first. Use a space's numerical id.\n\n"
              f"Find space IDs using {RESET}\n"
              f"   {APP_HANDLE} spaces {BLUE}configured{RESET}\n")
        return 1

    COLUMNS = [
        {"key": "pid", "label": "PAGE ID", "width": 11},
        {"key": "depth", "label": "DEPTH", "width": 14},
        {"key": "direct_children", "label": "CHILDREN", "width": 8},
        {"key": "descendants", "label": "DESCENDANTS", "width": 11},
        {"key": "avg_word_count", "label": "AVG WORDS", "width": 9},
        {"key": "most_common_type", "label": "COMMON DESC. TYPES", "width": 20},
        {"key": "title", "label": "TITLE"},
    ]
    print()
    print("=" * WIDTH_NICE)
    space_alias = get_space_attribute(args.space_id, 'id', 'alias')
    print(f"Finding interesting entry points for space {space_alias} ({args.space_id}):\n")
    cartography_results = make_maps(args.space_id, limit=args.limit)

    render_table(cartography_results, COLUMNS)
    return 0