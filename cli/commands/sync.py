# Sync: store an offline copy of page data from Confluence
# optionally restart from a set step
# optionally hard refresh

def register(subparsers):
    p = subparsers.add_parser("sync", help="Sync pages from your Confluence Cloud to your local database in ccandle")
    p.add_argument("--hard-refresh", action="store_true", help="Sync all pages from scratch, even if they have not changed since last sync")

def run(args):
    from sync.sync_all import sync
    from network.network_utils import check_network_connection
    if not check_network_connection():
        return 1
    sync(args.hard_refresh)
    return 0
