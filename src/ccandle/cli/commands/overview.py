# Fast overview of Confluence space quality, connectedness, and navigability.

def register(subparsers):
    p = subparsers.add_parser("overview", help="Learn quick stats on your configured Confluence spaces")
    p.add_argument("--space-id", help="Narrow overview to just one space")
    p.add_argument("--quiet", "-q", action="store_true", default=False,
                        help="Mute verbose explanations")

def run(args):
    from ccandle.analysis.space_overview import present_all_space_overviews, present_space_overview
    if args.space_id:
        present_space_overview(space_id=args.space_id, quiet=args.quiet)
    else:
        present_all_space_overviews(quiet=args.quiet)
    return 0

