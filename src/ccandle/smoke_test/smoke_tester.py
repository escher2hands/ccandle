import subprocess, time

from ccandle.config.config_app import APP_NAME
from ccandle.presentation.theme import YELLOW, GREEN, BLUE, RESET, WIDTH_NICE

BASE_CMD = [f"{APP_NAME}"]

def interactive_smoke_test():
    print(f"\n{BLUE}" + "=" * WIDTH_NICE)
    print(f"This will run through most of the commands in this toolset.\n"
          "To ensure the commands work fine on your local system, you'll want to set test values for a few things.\n")
    print(f"Set your own test values? Y/n")
    yes = input().strip().lower()
    if yes in ("y", "yes"):
        print(f"Please input two test page IDs:")
        test_pid_1, test_pid_3 = input()
        print("...and a second page ID:")
        test_pid_2 = input()
        print(f"Please input a test space ID (id of a Confluence space you are tracking):")
        test_space_id = input()
        print(f"Please input some test space short name fragment to search for:")
        test_space_query = input()
        print(f"Please input a test navbox name:")
        test_nav_name = input()
        print(f"Please input a test label name:")
        test_label = input()
    else:
        test_pid_1 = '1471579641'
        test_pid_2 = '2396061709'
        test_pid_3 = '2872869089'
        test_space_id = 'bd1'
        test_space_query = 'but'
        test_nav_name = "admin portal navbox"
        test_label = "ddd"

    print(f"{RESET}")

    TEST_COMMANDS = [
        BASE_CMD + ["spaces"],                   # default input
        BASE_CMD + ["spaces", "list"],
        BASE_CMD + ["spaces", "list", "--filter", test_space_query],
        BASE_CMD + ["spaces", "configured"],

        BASE_CMD + ["sync", "--quiet"],
        BASE_CMD + ["sync", "--from-step", "parse_text", "--quiet"],

        BASE_CMD + ["labels", "list", "--space", f"{test_space_id}"],
        BASE_CMD + ["labels", "mentions", f"{test_label}"],
        BASE_CMD + ["labels", "mentions", f"{test_label}", "--space", f"{test_space_id}"],
        BASE_CMD + ["labels", "suggest-merges", "--limit", "10"],
        BASE_CMD + ["labels", "add", "smoke-test-label", f"{test_pid_2}", f"{test_pid_3}"],
        BASE_CMD + ["labels", "remove", "smoke-test-label", f"{test_pid_2}", f"{test_pid_3}"],

        BASE_CMD + ["excerpts", "list", "--limit", "10"],
        BASE_CMD + ["excerpts", "list", "--space", f"{test_space_id}", "-l", "15"],
        BASE_CMD + ["excerpts", "list", "--sources-only", "-l", "10"],
        BASE_CMD + ["excerpts", "list", "--navboxes-only", "-l", "10"],


        BASE_CMD + ["stats", "authors", "--space", f"{test_space_id}", "--limit", f"{10}"],

        BASE_CMD + ["stats", "links", "popular", "--space", f"{test_space_id}", "--limit", f"{5}"],
        BASE_CMD + ["stats", "links", "orphans", "--space", f"{test_space_id}", "--limit", f"{5}"],
        BASE_CMD + ["stats", "links", "incoming", f"{test_pid_1}", "--limit", f"{5}"],
        BASE_CMD + ["stats", "links", "cross-space", "--space", f"{test_space_id}", "--limit", f"{5}"],
        BASE_CMD + ["stats", "links", "cross-space", "--space", f"{test_space_id}", "--ids"],

        BASE_CMD + ["stats", "empty", "blanks", "--space", f"{test_space_id}", "-l", f"{5}"],
        BASE_CMD + ["stats", "empty", "wordless", "--space", f"{test_space_id}", "-l", f"{5}"],
        BASE_CMD + ["stats", "empty", "stubs", "--space", f"{test_space_id}", "-l", f"{5}"],
        BASE_CMD + ["stats", "empty", "blanks", "--no-structural-value", "-l", f"{5}"],
        BASE_CMD + ["stats", "empty", "wordless", "-nsv", "-l", f"{5}"],
        BASE_CMD + ["stats", "empty", "stubs", "--ids", "-l", f"{5}"],

        BASE_CMD + ["stats", "children", f"{test_pid_1}", "-l", f"{15}"],
        BASE_CMD + ["stats", "children", f"{test_pid_1}", "--ids", "-l", f"{5}"],


        BASE_CMD + ["cartographer", "--space", f"{test_space_id}", "-l", f"{5}"],


        BASE_CMD + ["sql", "query", "select id, labels, title from pages limit 10"],
        BASE_CMD + ["sql", "columns"],

        BASE_CMD + ["overview"],
        BASE_CMD + ["overview", "--space", f"{test_space_id}"],
        BASE_CMD + ["overview", "--corpus"],


        BASE_CMD + ["benchmark", "snapshots", "list"],
    ]

    return smoke_test(test_commands=TEST_COMMANDS)

def smoke_test(test_commands):
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
            stderr=subprocess.STDOUT,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        # Default answer for any input() prompts
        process.stdin.write("y\n")
        process.stdin.flush()
        process.stdin.close()

        # Stream output live
        for line in process.stdout:
            print(line, end="")

        # Wait for process to finish
        process.wait()

        elapsed = time.time() - start

        if process.returncode != 0:
            cmd_status = "FAILED"
            COLOR = YELLOW
            failures += 1
        else:
            cmd_status = "OK"
            COLOR = GREEN

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
