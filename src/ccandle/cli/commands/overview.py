# Fast overview of Confluence space quality, connectedness, and navigability.
from ccandle.presentation.user_communication import clean_user_space_id_or_exit


def register(subparsers):
    p = subparsers.add_parser("overview", help="Evaluate quality metrics on your configured Confluence spaces")
    p.add_argument("--space", help="Narrow overview to just one space")
    p.add_argument("--quiet", "-q", action="store_true", default=False,
                        help="Mute verbose explanations")
    p.add_argument("--corpus", action="store_true", default=False,
                        help="Get an overall combined evaluation across all spaces, instead of individual evaluations per space (total across population vs. per space)")

def run(args):
    from ccandle.analysis.space_overview import present_all_space_overviews, present_space_overview
    space_id = clean_user_space_id_or_exit(args.space)
    if space_id or args.corpus:
        present_space_overview(space_id=space_id, quiet=args.quiet)
    else:
        present_all_space_overviews(quiet=args.quiet)
    return 0

