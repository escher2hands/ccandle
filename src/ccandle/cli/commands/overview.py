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
    from ccandle.analysis.space_overview import present_all_space_overviews, present_space_overview
    space_id = clean_user_space_id_or_exit(args.space)
    if space_id or args.corpus:
        results = present_space_overview(space_id=space_id, quiet=args.quiet, json_format=args.json)
    else:
        results = present_all_space_overviews(quiet=args.quiet, json_format=args.json)

    if args.json:
        print(json.dumps(results, indent=2))
    return 0

