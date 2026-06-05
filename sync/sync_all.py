# currently we only scrape pages metadata and html...
# later we'll add more steps.
from children.scrape_children import scrape_children
from db.db_utils import get_all_ids_in_pages
from db.table_utils import create_table
from pages.schema_table_pages import SCHEMA_PAGES
from pages.scrape_list_of_available_pages import scrape_page_metadata_in_space
from pages.scrape_page_htmls import scrape_page_contents_from_server
from presentation.theme import WIDTH_NICE, DIM, RESET
from spaces.space_utils import list_configured_space_ids, get_space_attribute
import datetime

VALID_STEPS = ["children", "authors", "labels", "parse_text", "convert_links"]

def sync(hard_refresh=False, resume_at=None):
    if not resume_at:
        delta_pages = sync_pages(hard_refresh=hard_refresh)               # run our first page scraping from the CC
    else:
        print(f"{DIM}Skipping step {RESET}scrape{DIM} pages from Confluence\n"
              f"{DIM}Processing all ids from local database{RESET}")
        delta_pages = get_all_ids_in_pages()                              # take pages to process from our local

    steps = [
        ("children", lambda: _scrape_children(delta_pages)),
        ("authors", lambda: _scrape_authors(delta_pages)),
        ("labels", lambda: _scrape_labels()),
        ("parse_text", lambda: _extract_plain_texts_in_bulk(delta_pages)),
        ("convert_links", lambda: _clean_link_formatting_and_store_link_list(delta_pages)),
        #("assign_type", lambda: _assign_page_type_in_bulk(to_process_list)),
        #("mentions", lambda: _scrape_and_store_all_mentions(to_process_list)),   # must go after assign type, as we don't care about mentions on useless page types
        #("vectorize", lambda: _embed_pages_as_vectors(to_process_list)),
        #("keyword", lambda: _run_fingerprinting(to_process_list)),
        #("map_links", lambda: _find_link_events_for_all_pages()),        # can only be done on all pages, no subsets
        #("duplicates", lambda: _find_duplicates()),                      # can only be done on all pages, no subsets
    ]
    for name, fn in steps:
        if resume_at and name != resume_at:
            print(f"{DIM}Skipping step {RESET}{name}")
            continue
        resume_at = None  # clear once reached
        step_start_time = datetime.datetime.now(datetime.timezone.utc)
        print(f"--------------------------------")
        print(f"Running step: {name}")
        fn()
        _print_step_duration(step_start_time, name)

    set_all_pages_as_processed(delta_pages)


def sync_pages(hard_refresh=False):
    create_table("pages", SCHEMA_PAGES)  # this does nothing if the table already exists

    space_ids = list_configured_space_ids()
    delta_pages = []
    for space_id in space_ids:
        space_name = get_space_attribute(space_id, "id", "alias")
        print("-" * WIDTH_NICE)
        print(f"Scraping page metadata for space {space_name.upper()} ({space_id})...\n")
        results = scrape_page_metadata_in_space(space_id, hard_refresh=hard_refresh)

        pids = results["pids"]
        print(f"Stored metadata for {results['stored_count']} pages.\n")
        if results['skipped_count'] != 0:
            print(f"Skipping {results['skipped_count']} pages, as they have not changed since your last sync.\n")
        else:
            print(f"Storing everything, as you chose to hard refresh your database.")

        if results['stored_count'] == 0:
            continue  # skip this space, as nothing has changed
        print("Now syncing page contents...")
        scrape_page_contents_from_server(pids)
        print(f"Successfully stored page contents for {results['stored_count']} pages.")

        delta_pages.extend(pids)
    return delta_pages

# - STEPS ----------------------------------------------
def _scrape_children(delta_pages):
    from children.scrape_children import scrape_children
    scrape_children(delta_pages)
def _scrape_authors(delta_pages):
    from authors.scrape_authors import scrape_authors
    scrape_authors(delta_pages)
def _scrape_labels():
    from labels.scrape_labels import scrape_labels
    scrape_labels()
def _extract_plain_texts_in_bulk(delta_pages):
    from pages.parsing.plain_text_extractor import extract_plain_texts_in_bulk
    extract_plain_texts_in_bulk(delta_pages)
def _clean_link_formatting_and_store_link_list(delta_pages):
    from pages.parsing.link_parser import clean_and_store_links
    clean_and_store_links(delta_pages)

def set_all_pages_as_processed(processed_list):
    from config.config_db import TABLE_PAGES, PATH_DB
    import sqlite3
    with sqlite3.connect(PATH_DB) as conn:
        cur = conn.cursor()
        cur.executemany(
            f"UPDATE {TABLE_PAGES} "
            "SET processed_version = version "
            "WHERE id = ?",
            ((pid,) for pid in processed_list)
        )

def _print_step_duration(step_start_time, name):
    step_duration = datetime.datetime.now(datetime.timezone.utc) - step_start_time
    duration_str = str(step_duration).split('.')[0]                 # Format duration as H:MM:SS
    print(f"Finished step {name} in {duration_str} (H:MM:SS).")


