# compare a snapshot stored locally to your current active db.
# see a delta between the 'overview' metrics between the snapshot
# and your current, to benchmark results and progress.
from ccandle.presentation.theme import *
import re
from pathlib import Path
from ccandle.config.config_db import ARTIFACT_DIR
import argparse

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

def validate_snapshot_date(value: str) -> str:
    """argparse type= validator: only accepts strict yyyy-mm-dd."""
    if not _DATE_RE.match(value):
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid date — expected format: yyyy-mm-dd")
    return value

def register(subparsers):
    p = subparsers.add_parser(
        "benchmark",
        help="Measure progress between your current local Confluence mirror and an old snapshot",
    )
    p.add_argument("--snapshot", default=None, help="The snapshot you'd like to compare against your current mirror")
    p.add_argument("--quiet", action="store_true", help="Suppress info")

    # nested, OPTIONAL subparsers -- omitting `required=True` here is what lets
    # `ccandle benchmark` run on its own with no subcommand
    benchmark_subparsers = p.add_subparsers(dest="bench_cmd")

    snapshots_p = benchmark_subparsers.add_parser("snapshots", help="Manage benchmark snapshots")
    # this level IS required -- "ccandle benchmark snapshots" alone doesn't make sense
    snap_sub = snapshots_p.add_subparsers(dest="snap_cmd", required=True)

    list_p = snap_sub.add_parser("list", help="List available snapshots")

    delete_p = snap_sub.add_parser("delete", help="Delete a snapshot")
    delete_p.add_argument("date", metavar="DATE", type=validate_snapshot_date, help="Date of the snapshot to delete (yyyy-mm-dd)")

    dehydrate_p = snap_sub.add_parser("dehydrate", help="Dehydrate a snapshot")
    dehydrate_p.add_argument("date", metavar="DATE", type=validate_snapshot_date, help="Date of the snapshot to dehydrate (yyyy-mm-dd)")

    create_p = snap_sub.add_parser("create", help="Create a new snapshot")

    frequency = snap_sub.add_parser("frequency", help="Set the snapshot frequency")
    frequency.add_argument("days", metavar="DAYS", type=int, help="Number of days between snapshots")

def run(args):
    from ccandle.benchmark.snapshot_manager import find_available_snapshots
    snap_cmd = getattr(args, "snap_cmd", None)
    
    if args.bench_cmd == "snapshots":
        if snap_cmd == "frequency":
            from ccandle.config.confluence_auth import set_conf_details
            return set_conf_details("snapshot-frequency", args.days)
        elif snap_cmd == "list":
            available_snaps = find_available_snapshots()
            display_snapshot_list(available_snaps, number_options=False)
            return 0
        elif snap_cmd == "delete":
            delete_snapshot(args.date)
            return 0
        elif snap_cmd == "dehydrate":
            dehydrate_snapshot(args.date)
            return 0
        elif snap_cmd == "create":
            from ccandle.benchmark.snapshot_manager import copy_and_dehydrate_snapshot
            from ccandle.config.config_db import PATH_DB
            copy_and_dehydrate_snapshot(PATH_DB)
            print("Successfully copied your current local pages into a snapshot.")
            return 0
        return 1

    # if none of those others, we assume bare benchmarking
    from ccandle.benchmark.do_benchmarking import compare_snapshots
    from ccandle.overview.present_space_overview import print_space_header, print_grouped, print_meta, print_type_header
    from ccandle.spaces.space_utils import display_friendly_space_info
    snapshot_ref = args.snapshot
    if not snapshot_ref:
        if not args.quiet:
            print(f"{DIM}Compare your current local copy of your tracked Confluence \n"
                  f"spaces against a stored snapshot from an older date.\n{RESET}")
        available_snaps = find_available_snapshots()
        options = display_snapshot_list(available_snaps)
        snapshot_ref = prompt_for_snapshot(options)
        if not snapshot_ref:
            print(f"{RED}No snapshot given.{RESET}")
            return 1
    comparison = compare_snapshots(snapshot_ref, json_format=False, quiet=args.quiet)

    for space in comparison['matched']:
        print_space_header(space['space_id'])
        print_meta(space['stats'], format_value=lambda k, v: _format_absolute_delta(v))
        print()
        print_grouped(space['stats'], args.quiet, lambda k, cfg, v: _format_delta_percent(v))
        print()
        print_type_header()
        print_page_types_delta(space['page_types'])
        print("\n")

    if comparison["only_in_snapshot"]:
        print(f"\nThe following spaces were in your {BLUE}snapshot{RESET}, but missing from the current db:")
        for space in comparison["only_in_snapshot"]:
            print(f"-   {DIM}{display_friendly_space_info(space['space_id'], long=True)}{RESET}")

    if comparison["only_in_current"]:
        print(f"\nThe following spaces were in your {BLUE}current db{RESET}, but missing from the snapshot:")
        for space in comparison["only_in_current"]:
            print(f"-   {DIM}{display_friendly_space_info(space['space_id'], long=True)}{RESET}")

    return 0


def display_snapshot_list(available: dict, number_options: bool=True):
    hydrated = available["hydrated"]
    dehydrated = available["dehydrated"]

    dehydrated_only = sorted(set(dehydrated) - set(hydrated), reverse=True)
    hydrated_dates = sorted(hydrated, reverse=True)
    options = []
    if hydrated_dates or dehydrated_only:
        print("Available snapshots:")

        index = 1
        for d in hydrated_dates:
            num_index = f"{BOLD}[{index}]{RESET}" if number_options else ""
            print(f"{num_index} -   {YELLOW}{d.isoformat()}{RESET}")
            options.append(d.isoformat())
            index += 1

        for d in dehydrated_only:
            num_index = f"{BOLD}[{index}]{RESET}" if number_options else ""
            print(
                f"{num_index} -   {d.isoformat()}"
                f"{DIM} (dehydrated only — will finish hydrating on use){RESET}"
            )
            options.append(d.isoformat())
            index += 1
    else:
        print(f"{DIM}No snapshots found yet. \n"
            f"Pass a path to a raw Confluence export to build one.{RESET}")
    return options

def prompt_for_snapshot(options: list):
    print(f"\n{DIM}Enter a snapshot number, or paste a snapshot path.\n"
        f"Type {RESET}{BOLD}q{RESET}{DIM} to cancel.{RESET}")
    while True:
        response = input("> ").strip()
        if response.lower() in ("q", "quit", "exit", "n", "no"):
            return None

        if response.isdigit():
            choice = int(response)
            if 1 <= choice <= len(options):
                return options[choice - 1]

            print(f"{DIM}Please enter a number from {RESET}1-{len(options)}{RESET}")
            continue
        # Anything non-numeric is assumed to be a path or explicit snapshot name.
        return response

def print_grouped_delta_stats(delta_stats, quiet=False):
    from ccandle.overview.generate_space_overview import STATS_GROUPS, STATS_GROUP_TITLES, STATS_KEYS

    for group in STATS_GROUPS:
        print(f"\n{STATS_GROUP_TITLES[group]}")
        print("-" * WIDTH_NICE)

        for key, cfg in STATS_KEYS.items():
            if cfg.group != group:
                continue

            delta = delta_stats.get(key)
            if delta is None:
                continue

            line = f"{cfg.title:<27}: {_format_delta_percent(delta):>16}"
            if not quiet and cfg.hint:
                line += f"  {DIM}→ {cfg.hint}{RESET}"

            print(line)

def _format_delta_percent(delta):
    EQUALITY_THRESHOLD = 0.001
    if abs(delta) < EQUALITY_THRESHOLD:
        return f"{DIM}    ---  {RESET}"

    colour = GREEN if delta > 0 else RED
    symbol = "▲" if delta > 0 else "▼"
    return f"{colour}{symbol} {abs(delta) * 100:5.1f} %{RESET}"

def _format_absolute_delta(value, width=6):
    if value == 0:
        return f"{DIM}--{RESET}".rjust(width)
    symbol = "▲" if value > 0 else "▼"
    return f"{symbol} {abs(value):>{width}}"

def print_page_types_delta(page_types_delta):
    for p_type, delta_count in page_types_delta.items():
        print(f"{_format_page_type_delta(delta_count):<20}{p_type}")

def _format_page_type_delta(delta_count, width=5):
    symbol = ""
    if delta_count > 0:
        symbol = "▲"
    elif delta_count < 0:
        symbol = "▼"
    if delta_count == 0:
        return " " * width + " " * 7
    return f"{symbol} {abs(delta_count):>{width}} pages"

def _snapshot_path(date_str: str, kind: str) -> Path:
    file_date = date_str.replace("-", "_")
    return ARTIFACT_DIR / f"confluence_mirror_{file_date}.{kind}.db"

def delete_snapshot(date_str: str) -> int:
    hydrated = _snapshot_path(date_str, "hydrated")
    dehydrated = _snapshot_path(date_str, "dehydrated")

    found = False
    for path in (hydrated, dehydrated):
        if path.exists():
            path.unlink()
            found = True
            print(f"{DIM}Removed {path.name}{RESET}")

    if not found:
        print(f"{RED}Couldn't find a snapshot with that date.{RESET}")
        return 1

    print(f"Deleted snapshot from {date_str}")
    return 0

def dehydrate_snapshot(date_str: str) -> int:
    hydrated = _snapshot_path(date_str, "hydrated")

    if not hydrated.exists():
        print(f"{RED}Couldn't find a snapshot with that date.{RESET}")
        return 1

    hydrated.unlink()
    print(f"Dehydrated snapshot from {date_str}")
    return 0
