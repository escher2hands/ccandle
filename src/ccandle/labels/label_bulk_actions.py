# goal is to create an interactive flow so users can define
# a list of page ids and a label, and get it added in bulk
# to those IDs.
from ccandle.labels.schema_table_labels import get_labels_cache
from ccandle.db.db_utils import update_field
from ccandle.db.db_query_utils import query_field_in_pages
from ccandle.network.network_utils import add_label_via_rest, delete_label_via_rest
from ccandle.presentation.theme import RED, YELLOW, RESET, BOLD, DIM
from rapidfuzz import fuzz
from tqdm import tqdm
import json

def add_label_to_pages(pids, clean_label):
    failures = []
    for pid in tqdm(pids, desc="Adding labels to pages...", unit="page"):
        status = add_label_via_rest(pid, clean_label)
        if not rest_success(status, clean_label):
            failures.append(pid)
        else:
            add_label_to_page_entry_in_db(pid, clean_label)
    return failures

def delete_label_from_pages(pids, clean_label):
    failures = []
    for pid in tqdm(pids, desc="Deleting labels from pages...", unit="page"):
        status = delete_label_via_rest(pid, clean_label)
        if status['status'] == 'absent':
            failures.append(str(pid) + " label was already absent")
        elif status['status'] == 'error':
            failures.append(str(pid) + " unknown error")
        else:
            delete_label_from_page_entry_in_db(pid, clean_label)
    return failures

def rest_success(response, your_label):
    confirmed_list = response.get("results")
    confirmed_labels = [confirmed['label'] for confirmed in confirmed_list]
    if your_label in confirmed_labels:
        return True

    return False

def normalize_label(original_label):
    label = original_label.strip().lower()
    if "_" in label or " " in label:
        legal_option = label.replace(" ", '-').replace(".", "'").replace(",", "'").replace('"', "'")
        better_option = legal_option.replace("_", '-')
        print(f"{DIM}Your label {RESET}{RED}{original_label}{RESET}{DIM} doesn't match Confluence's style guide for labels.\n"
              f"Use {RESET}{BOLD}{better_option}{RESET}{DIM} instead? Y/n{RESET}")
        response = input().strip().lower()
        if response in ("y", "yes"):
            return better_option
        label = legal_option
    return label

def fuzzy_resolve_label_name(clean_label, existing_labels: list[str], top_k: int = 3):
    scored = []

    for label in existing_labels:
        if label == clean_label:
            continue
        score = fuzz.WRatio(clean_label, label)
        scored.append((label, score))

    # sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    # optional threshold: avoids garbage suggestions
    MIN_SCORE = 75
    filtered = [lbl for lbl, s in scored if s >= MIN_SCORE]

    return filtered[:top_k]

def check_and_clean_label(label):
    LABELS_CACHE = get_labels_cache()
    label = normalize_label(label)
    fuzzies = fuzzy_resolve_label_name(label, LABELS_CACHE)

    if fuzzies is not None and fuzzies != [] and label not in fuzzies:
        print(f"\n{DIM}Your cleaned label {RESET}{BOLD}{label}{RESET}{DIM} seems similar to a few existing labels:{RESET}")
        index = 1
        print(f"{BOLD}{0}{RESET} -   {label}{RESET}{DIM} (your label){RESET}")
        for fuzzy_label in fuzzies:
            print(f"{BOLD}{index}{RESET} -   {YELLOW}{fuzzy_label}{RESET}")
            index += 1
        print(f"{DIM}Press the number of the label you want to use. \n"
              f"Or, press {RESET}{BOLD}0{RESET}{DIM} to create a new label with your input.{RESET}")
        while True:
            response = input().strip().lower()
            if response in ["exit", "n", "no"]:
                print("Exiting...")
                return None
            response_int = int(response) if response.isdigit() else 999
            if response == "0":
                return label
            elif 0 <= response_int <= len(fuzzies) + 1:
                return fuzzies[response_int-1]
            else:
                print(f"{DIM}Please enter a number from {RESET}0-3")
    return label

def add_label_to_page_entry_in_db(pid, label):
    page_labels = query_field_in_pages(pid, "labels")
    label_set = set(json.loads(page_labels))
    label_set.add(label)
    updated_labels = json.dumps(sorted(label_set))

    update_field(pid, "labels", updated_labels)

def delete_label_from_page_entry_in_db(pid, label):
    page_labels = query_field_in_pages(pid, "labels")
    print(page_labels)
    label_set = set(json.loads(page_labels))
    label_set.discard(label)
    updated_labels = json.dumps(sorted(label_set))
    update_field(pid, "labels", updated_labels)
