# compare a snapshot stored locally to your current active db.
# see a delta between the 'overview' metrics between the snapshot
# and your current, to benchmark results and progress.

from ccandle.config.config_db import TABLE_PAGES, PATH_DB
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("benchmark", help="Measure progress between your current local Confluence mirror and an old snapshot")

    p.add_argument("SNAPSHOT_NAME_OR_PATH", help="The snapshot you'd like to compare against your current mirror")


def run(args):
    from ccandle.benchmark.do_benchmarking import compare_snapshots
    return compare_snapshots(args.SNAPSHOT_NAME_OR_PATH)
