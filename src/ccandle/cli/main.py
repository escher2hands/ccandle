import argparse
from ccandle.presentation.theme import *
from ccandle.cli.commands import connection, spaces, sync, overview, labels, sql, stats, preview, cartographer, excerpts
from ccandle.cli.commands import smoke_test

COMMANDS = [connection, spaces, sync, overview, stats, sql, labels, excerpts, preview, cartographer, smoke_test]  # just add new modules here as you grow

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="cli", description=f"{BLUE}Bulk knowledge management for Confluence Cloud.{RESET}")
    subparsers = parser.add_subparsers(dest="cmd", required=True)

    for cmd in COMMANDS:
        cmd.register(subparsers)

    args = parser.parse_args(argv)

    for cmd in COMMANDS:
        if args.cmd == cmd.__name__.split(".")[-1].replace("_", "-"):  # matches "space", "connection", etc.
            return cmd.run(args)

    return 2

if __name__ == "__main__":
    raise SystemExit(main())