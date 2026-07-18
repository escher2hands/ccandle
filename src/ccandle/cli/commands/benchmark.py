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

    return compare_snapshots(
        snapshot_ref,
        json_format=False,
        quiet=args.quiet,
    )

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