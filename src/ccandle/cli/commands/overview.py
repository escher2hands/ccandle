# Fast overview of Confluence space quality, connectedness, and navigability.
import json

from ccandle.presentation.user_communication import clean_user_space_id_or_exit


def register(subparsers):
    p = subparsers.add_parser("overview", help="Evaluate quality metrics on your configured Confluence spaces")
    p.add_argument("--space", help="Narrow overview to just one space")
    p.add_argument("--quiet", "-q", action="store_true", default=False,
                        help="Mute verbose explanations")
    p.add_argument("--corpus", action="store_true", default=False,
                        help="Get an overall combined evaluation across all spaces, instead of individual evaluations per space (total across population vs. per space)")
    p.add_argument("--json", action="store_true", default=False, help="Output in easy parseable JSON format")

def run(args):
    from ccandle.overview.generate_space_overview import generate_all_space_overviews, generate_space_overview
    from ccandle.overview.present_space_overview import print_space_overview
    space_id = clean_user_space_id_or_exit(args.space)
    if space_id or args.corpus:
        results = [generate_space_overview(space_id=space_id)]
    else:
        results = generate_all_space_overviews()

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_space_overview(results)
    return 0

