from ccandle.presentation.theme import *
from ccandle.db.db_utils import ids_multi_exist_in_table
from ccandle.config.config_app import APP_HANDLE

def get_confirmation_to_continue(msg=None, acceptable_confirmations=None):
    msg = msg or "Type yes or no. Y/n"
    acceptable_confirmations = acceptable_confirmations or ["y", "yes"]
    print(f"\n{DIM}{msg}{RESET}")
    response = input()
    if response not in acceptable_confirmations:
        print("Aborting.")
        exit(0)


def exit_if_not_all_ids_are_in_db(target_pids, source_pid=None):
    target_pids = target_pids + [source_pid] if source_pid else target_pids
    id_list_existence = ids_multi_exist_in_table(target_pids)
    if not id_list_existence['all_exist']:
        print(f"{RED}" + "-" * WIDTH_NICE + "\n" +
              f"Invalid page IDs.\n")
        if id_list_existence['failed_ids'] == set():
            if source_pid in id_list_existence['duplicates']:
                print(f"{DIM}Your source page ID ({RESET}{BOLD}{source_pid}{RESET}{RED}{DIM}) is also in your list of targetted page IDs.")
            else:
                print(f"{DIM}You entered a page ID list with duplicates: ({RESET}{BOLD}{id_list_existence['duplicates']}{RESET}{RED}{DIM})")
        else:
            print(f"{DIM}Some ({RESET}{BOLD}{len(id_list_existence['failed_ids'])}{RESET}{RED}{DIM}) of the ids you specified does not seem \n"
                  f"to be in your local scraped Confluence pages:\n"
                  f"{RESET}- {id_list_existence['failed_ids']}\n\n"
                  f"{RED}{DIM}Try running \n"
                  f"   {RESET}{BLUE}{APP_HANDLE} sync{RESET}\n"
                  f"{RED}{DIM}to fetch the latest pages in Confluence, or double check \n"
                  f"that the pages you listed belong to Confluence spaces you track.")
        exit(1)
