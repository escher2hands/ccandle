from ccandle.presentation.theme import *


def register(subparsers):
    p = subparsers.add_parser("cartographer", help="Discover the layout and distribution of content in your Confluence spaces")
    p.add_argument("--space", help="Narrow overview to just one space")
    p.add_argument("--quiet", "-q", action="store_true", default=False,
                        help="Mute verbose explanations")
    p.add_argument("--limit", "-l", type=int, default=25, help="Limit to top N results")

def run(args):
    from ccandle.analysis.stats_cartography import make_maps
    from ccandle.analysis.cartography_visualizer import render_pages_map_in_browser
    from ccandle.presentation.user_communication import clean_user_space_id_or_exit, get_confirmation_to_continue
    from ccandle.config.config_app import APP_HANDLE
    from ccandle.presentation.page_previews import render_table
    from ccandle.spaces.space_utils import display_friendly_space_info

    space_id = clean_user_space_id_or_exit(args.space)       # clean our space identifier input, and exit if invalid
    if space_id is None:
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
    print(f"\n{DIM}Finding interesting entry points for space {RESET}{display_friendly_space_info(space_id, color=True)}:\n")
    cartography_results = make_maps(space_id, limit=args.limit)

    render_table(cartography_results, COLUMNS)

    print("\n" + "-" * WIDTH_NICE + "\n"
          "Would you like to see this visualized in a web graph?")
    get_confirmation_to_continue()
    for m in cartography_results:
        m['subtree_quality'] = 1
        m['quality'] = 1

    render_pages_map_in_browser(cartography_results, space_id=space_id)

    return 0