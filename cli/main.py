import argparse
from presentation.theme import *
from cli.commands import connection, spaces, labels, sync, smoke_test, sql, stats, overview

COMMANDS = [connection, spaces, labels, sync, smoke_test, sql, stats, overview]  # just add new modules here as you grow

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