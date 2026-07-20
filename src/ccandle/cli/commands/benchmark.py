# compare a snapshot stored locally to your current active db.
# see a delta between the 'overview' metrics between the snapshot
# and your current, to benchmark results and progress.
from ccandle.presentation.theme import *

def register(subparsers):
    p = subparsers.add_parser("benchmark", help="Measure progress between your current local Confluence mirror and an old snapshot")

    p.add_argument("--snapshot", default=None, help="The snapshot you'd like to compare against your current mirror")
    p.add_argument("--quiet", action="store_true", help="Suppress info")

def run(args):
    from ccandle.benchmark.snapshot_manager import find_available_snapshots
    from ccandle.benchmark.do_benchmarking import compare_snapshots
    from ccandle.overview.present_space_overview import print_space_header, print_grouped, print_meta, print_type_header
    from ccandle.spaces.space_utils import display_friendly_space_info

    snapshot_ref = args.snapshot
    if not snapshot_ref:
        if not args.quiet:
            print(f"{DIM}Compare your current local copy of your tracked Confluence \n"
                  f"spaces against a stored snapshot from an older date.\n{RESET}")
        available_snaps = find_available_snapshots()
        snapshot_ref = prompt_for_snapshot(available_snaps)
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

def prompt_for_snapshot(available: dict):
    hydrated = available["hydrated"]
    dehydrated = available["dehydrated"]

    dehydrated_only = sorted(set(dehydrated) - set(hydrated), reverse=True)
    hydrated_dates = sorted(hydrated, reverse=True)

    options = []

    if hydrated_dates or dehydrated_only:
        print("Available snapshots:")

        index = 1
        for d in hydrated_dates:
            print(f"{BOLD}[{index}]{RESET} -   {YELLOW}{d.isoformat()}{RESET}")
            options.append(d.isoformat())
            index += 1

        for d in dehydrated_only:
            print(
                f"{BOLD}[{index}]{RESET} -   "
                f"{d.isoformat()}"
                f"{DIM} (dehydrated only — will finish hydrating on use){RESET}"
            )
            options.append(d.isoformat())
            index += 1
    else:
        print(f"{DIM}No snapshots found yet. \n"
            f"Pass a path to a raw Confluence export to build one.{RESET}")

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
