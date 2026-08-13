"""
Algorithmically generates CLI command permutations for the `stats` branch by
introspecting the real argparse parser (the same `register()` your CLI uses),
instead of hand-listing commands. This means:

  - New subcommands/flags get tested automatically, no manual updates needed.
  - Flags used in tests are guaranteed to exist (they're read off the parser
    itself), so drift like a manually-typed `--ids-only` when the real flag
    is `--ids` becomes structurally impossible.

Usage:
    python generate_stats_permutations.py              # one-flag-at-a-time (fast)
    python generate_stats_permutations.py --exhaustive  # full Cartesian product per leaf
"""

import argparse
import itertools
import random
import sys
import time

from ccandle.config.config_app import APP_NAME
from ccandle.db.db_utils import random_pid_in_pages
from ccandle.presentation.theme import *
from ccandle.spaces.space_utils import list_configured_space_ids
from ccandle.cli.commands.stats import register as register_stats

BASE_CMD = [APP_NAME]


# ─── Value providers ──────────────────────────────────────────────────────
# Positional args MUST have a provider here (there's no sane default for
# "some page id"). Optional args fall back to STATIC_VALUES, then to the
# flag's own argparse default, then get skipped with a warning.

def _pid_provider():
    return random_pid_in_pages(1)[0]


def _space_provider():
    ids = list_configured_space_ids()
    return ids[random.randint(0, len(ids) - 1)]


DYNAMIC_VALUES = {
    "page_id": _pid_provider,
    "space": _space_provider,
}

STATIC_VALUES = {
    "limit": [3, 25],
    "fuzziness": [0.8, 1.2],
    "max_depth": [1, 3],
    "min_age": [0, 90],
}

# Flags to skip entirely (e.g. because testing a non-default value is
# meaningless without a second db to point at).
SKIP_DESTS = {"db_path"}


# ─── Parser introspection ─────────────────────────────────────────────────

def build_root_parser():
    root = argparse.ArgumentParser(prog=APP_NAME)
    subparsers = root.add_subparsers(dest="cmd", required=True)
    register_stats(subparsers)
    return root


def find_subparsers_action(parser):
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def walk_leaf_parsers(parser, path=()):
    """Yield (path_tuple, leaf_parser) for every terminal command.

    If a level's subcommand is optional (required=False, e.g. `orphans`
    defaulting to `breakdown`), the parent itself is yielded as a leaf too,
    so the "rely on the default" invocation gets exercised.
    """
    sub_action = find_subparsers_action(parser)
    if sub_action is None:
        yield path, parser
        return
    if not sub_action.required:
        yield path, parser
    for name, child_parser in sub_action.choices.items():
        yield from walk_leaf_parsers(child_parser, path + (name,))


def extract_fillable_actions(parser):
    positionals, optionals = [], []
    for action in parser._actions:
        if isinstance(action, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        if action.dest in SKIP_DESTS:
            continue
        (positionals if not action.option_strings else optionals).append(action)
    return positionals, optionals


# ─── Value resolution ──────────────────────────────────────────────────────

def resolve_positional_value(action):
    provider = DYNAMIC_VALUES.get(action.dest)
    if provider is None:
        raise ValueError(
            f"No value provider registered for positional arg '{action.dest}'. "
            f"Add one to DYNAMIC_VALUES."
        )
    return str(provider())


def resolve_optional_variants(action):
    """Return a list of token-lists (each a way to invoke this flag)."""
    flag = action.option_strings[0]

    if isinstance(action, (argparse._StoreTrueAction, argparse._StoreFalseAction)):
        return [[flag]]

    if action.dest in DYNAMIC_VALUES:
        return [[flag, str(DYNAMIC_VALUES[action.dest]())]]

    if action.dest in STATIC_VALUES:
        return [[flag, str(v)] for v in STATIC_VALUES[action.dest]]

    if action.default is not None:
        return [[flag, str(action.default)]]

    print(f"  [warn] no value source for optional '{action.dest}', skipping it")
    return []


# ─── Permutation generation ────────────────────────────────────────────────

def generate_variants(positionals, optionals, exhaustive=False):
    try:
        positional_tokens = [resolve_positional_value(a) for a in positionals]
    except ValueError as e:
        print(f"  [skip leaf] {e}")
        return

    # Each flag contributes a list of choices: "omit" plus each variant.
    per_flag_choices = [[[]] + resolve_optional_variants(a) for a in optionals]

    if exhaustive:
        combos = list(itertools.product(*per_flag_choices))
    else:
        combos = [tuple([] for _ in per_flag_choices)]  # baseline: all flags omitted
        for i, choices in enumerate(per_flag_choices):
            for variant in choices[1:]:
                combo = [[] for _ in per_flag_choices]
                combo[i] = variant
                combos.append(tuple(combo))

    seen = set()
    for combo in combos:
        flag_tokens = [tok for group in combo for tok in group]
        full = positional_tokens + flag_tokens
        key = tuple(full)
        if key not in seen:
            seen.add(key)
            yield full


def build_test_commands(exhaustive=False):
    root = build_root_parser()
    stats_action = find_subparsers_action(root)
    stats_parser = stats_action.choices["stats"]

    commands = []
    for path, leaf in walk_leaf_parsers(stats_parser, path=("stats",)):
        positionals, optionals = extract_fillable_actions(leaf)
        for arg_tokens in generate_variants(positionals, optionals, exhaustive=exhaustive):
            commands.append(BASE_CMD + list(path) + arg_tokens)
    return commands


# ─── Runner (reuses your existing smoke_test) ──────────────────────────────

def smoke_test(test_commands):
    import subprocess
    suite_start = time.time()
    failures = 0
    for cmd in test_commands:
        print("\n" + "=" * WIDTH_NICE * 2)
        print("RUNNING:", " ".join(cmd))
        print("=" * WIDTH_NICE * 2)
        start = time.time()
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        process.stdin.write("y\n")
        process.stdin.flush()
        process.stdin.close()
        for line in process.stdout:
            print(line, end="")
        process.wait()
        elapsed = time.time() - start
        if process.returncode != 0:
            cmd_status, COLOR, failures = "FAILED", YELLOW, failures + 1
        else:
            cmd_status, COLOR = "OK", GREEN
        print(f"\n{COLOR}" + "-" * 80 + "\n"
              f"EXIT CODE: {process.returncode}\n"
              f"DURATION : {elapsed:.2f}s\n"
              f"STATUS   : {cmd_status}\n"
              f"{RESET}")
    suite_elapsed = time.time() - suite_start
    print(f"\nTOTAL TEST SUITE DURATION : {suite_elapsed:.2f}s\n"
          f"   SUCCESSFUL: {len(test_commands) - failures}\n"
          f"   FAILED: {failures}\n")
    return failures


def algorithmic_smoke_test(exhaustive=False):
    commands = build_test_commands(exhaustive=exhaustive)
    mode = "exhaustive" if exhaustive else "one-flag-at-a-time"
    print(f"Generated {len(commands)} command permutations ({mode} mode).\n")
    return smoke_test(test_commands=commands)


if __name__ == "__main__":
    algorithmic_smoke_test(exhaustive="--exhaustive" in sys.argv)