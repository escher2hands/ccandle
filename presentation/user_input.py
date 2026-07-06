from presentation.theme import *

def get_confirmation_to_continue(msg=None, acceptable_confirmations=None):
    msg = msg or "Type yes or no. Y/n"
    acceptable_confirmations = acceptable_confirmations or ["y", "yes"]
    print(f"\n{DIM}{msg}{RESET}")
    response = input()
    if response not in acceptable_confirmations:
        print("Aborting.")
        exit(0)
