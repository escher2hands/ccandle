# Sync: store an offline copy of page data from Confluence
# optionally restart from a set step
# optionally hard refresh
from ccandle.sync.sync_all import VALID_STEPS, API_STEPS

def register(subparsers):
    p = subparsers.add_parser("sync", help="Sync pages from your Confluence Cloud to your local database in ccandle")
    p.add_argument("--hard-refresh", action="store_true", help="Sync all pages from scratch, even if they have not changed since last sync")
    p.add_argument("--from-step", dest="from_step", type=str, default=None,
                        help="Resume processing from the given step. Valid steps: " + ", ".join(VALID_STEPS),)

def run(args):
    from ccandle.sync.sync_all import sync
    from ccandle.network.network_utils import check_network_connection
    if args.from_step in API_STEPS + [None]:
        if not check_network_connection():
            return 1                # force internet connection for steps that require API connection
    sync(args.hard_refresh, args.from_step)
    return 0
