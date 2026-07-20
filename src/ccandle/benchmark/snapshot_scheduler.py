"""
Take a snapshot after a full `ccandle sync` (no flags), IF it's time to
take a new snapshot for benchmarking (according to configured
snapshot_frequency in days)

- Silent by default. A routine sync should stay quiet unless we actually
  take action -- no "checked and nothing to do" noise.
- We don't distinguish hydrated vs. dehydrated snapshots when deciding
  whether a new one is due -- only the most recent date matters.
- This module recomputes from find_available_snapshots() on every call
  rather than caching to a JSON file.
"""

from ccandle.config.confluence_auth import fetch_conf_details
from ccandle.presentation.theme import *
from ccandle.config.config_db import PATH_DB
import datetime

# Checks whether the most recent snapshot on file is older than the
# configured snapshot_frequency. If so, take a new snapshot. Else, nothing.
def maybe_take_scheduled_snapshot():
    frequency_days = fetch_conf_details("snapshot_frequency")
    if not frequency_days or frequency_days <= 0:
        return          # auto-snapshotting disabled

    from ccandle.benchmark.snapshot_manager import find_available_snapshots
    snapshots = find_available_snapshots()
    all_dates = snapshots.get("dehydrated", []) + snapshots.get("hydrated", [])
    latest_date = _get_latest_snapshot_date(snapshots)

    if latest_date is None:
        _take_snapshot_and_report(reason="no snapshots found yet")
        return

    days_since_last = (datetime.date.today() - latest_date).days
    if days_since_last >= frequency_days:
        _take_snapshot_and_report(
            reason=f"last snapshot was {days_since_last} days ago (frequency: {frequency_days}d)"
        )
    # else: within frequency window -- do nothing, silently.

def _get_latest_snapshot_date(date_strings):
    if not date_strings:
        return None
    dates = [datetime.date.fromisoformat(s) for s in date_strings]
    return max(dates)

def _take_snapshot_and_report(reason):
    from ccandle.benchmark.snapshot_manager import copy_and_dehydrate_snapshot

    print(f"{DIM}Auto-snapshot due {RESET}({reason}){DIM}. Taking a new snapshot...{RESET}")
    copy_and_dehydrate_snapshot(PATH_DB)
    print(f"{DIM}Snapshot complete.{RESET}")