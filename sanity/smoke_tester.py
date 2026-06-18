import subprocess, time
from presentation.theme import YELLOW, GREEN, BLUE, RESET, WIDTH_NICE

BASE_CMD = ["ccandle"]

def interactive_smoke_test():
    print(f"\n{BLUE}" + "=" * WIDTH_NICE)
    print(f"This will run through most of the commands in this toolset.\n"
          "To ensure the commands work fine on your local system, you'll want to set test values for a few things.\n")
    print(f"Set your own test values? Y/n")
    yes = input().strip().lower()
    if yes in ("y", "yes"):
        print(f"Please input a test page ID:")
        test_page_id = input()
        print(f"Please input a test space ID (id of a Confluence space you are tracking):")
        test_space_id = input()
        print(f"Please input some test space short name fragment to search for:")
        test_space_query = input()
        print(f"Please input a test navbox name:")
        test_nav_name = input()
    else:
        test_page_id = '1471579641'
        test_space_id = '601554991'
        test_space_query = 'but'
        test_nav_name = "on!track abc's navbox"

    print(f"{RESET}")

    TEST_COMMANDS = [
        BASE_CMD + ["spaces"],                   # default input
        BASE_CMD + ["spaces", "list"],
        BASE_CMD + ["spaces", "list", "--filter", test_space_query],
        BASE_CMD + ["spaces", "configured"],

        BASE_CMD + ["sync"],
        BASE_CMD + ["sync", "--from-step", "parse_text"],

        BASE_CMD + ["labels", "add", "smoke-test-label", "2622718175", "2455404674"],
        BASE_CMD + ["labels", "delete", "smoke-test-label", "2622718175", "2455404674"],

        BASE_CMD + ["sql", "query", "select id, labels, title from pages limit 15"],
        BASE_CMD + ["sql", "columns"],
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
