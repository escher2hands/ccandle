# Basic sanity check on cli commands.

def register(subparsers):
    p = subparsers.add_parser("smoke-test", help="Sanity check the CLI commands and functionality")

def run(args):
    from ccandle.smoke_test.smoke_tester import interactive_smoke_test
    return interactive_smoke_test()

