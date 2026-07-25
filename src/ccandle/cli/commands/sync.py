# Sync: store an offline copy of page data from Confluence
# optionally restart from a set step
# optionally hard refresh
from ccandle.sync.sync_all import VALID_STEPS, API_STEPS

def register(subparsers):
    p = subparsers.add_parser("sync", help="Sync pages from your Confluence Cloud to your local database in ccandle")
    p.add_argument("--hard-refresh", action="store_true", help="Sync all pages from scratch, even if they have not changed since last sync")
    p.add_argument("--from-step", dest="from_step", type=str, default=None,
                        help="Resume processing from the given step. Valid steps: " + ", ".join(VALID_STEPS),)
    p.add_argument("--space", default=None, help="Sync only a selected space")

def run(args):
    from ccandle.sync.sync_all import sync
    from ccandle.network.network_utils import check_network_connection
    from ccandle.presentation.user_communication import clean_user_space_id_or_exit
    from ccandle.benchmark.snapshot_scheduler import maybe_take_scheduled_snapshot

    space_id = clean_user_space_id_or_exit(args.space)       # clean our space identifier input, and exit if invalid

    if args.from_step in API_STEPS + [None]:
        if not check_network_connection():
            return 1                # force internet connection for steps that require API connection
    sync(hard_refresh=args.hard_refresh, resume_at=args.from_step, space_id=space_id)

    if not args.from_step and not space_id:
        maybe_take_scheduled_snapshot()

    return 0
