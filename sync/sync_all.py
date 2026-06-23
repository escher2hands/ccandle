# currently we only scrape pages metadata and html...
# later we'll add more steps.
from db.db_utils import get_all_ids_in_pages
from presentation.theme import WIDTH_NICE, DIM, RESET
import datetime

VALID_STEPS = ["children", "authors", "labels", "parse_text", "basic_stats", "convert_links", "excerpts",
               "assign_type", "find_duplicates"]

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
        ("basic_stats", lambda: _add_basic_metadata_in_bulk(delta_pages)),
        ("convert_links", lambda: _clean_link_formatting_and_store_link_list(delta_pages)),
        ("excerpts", lambda: _extract_excerpt_info(delta_pages)),
        ("assign_type", lambda: _type_all_pages(delta_pages)),
        #("mentions", lambda: _scrape_and_store_all_mentions(delta_pages)),   # must go after assign type, as we don't care about mentions on useless page types
        #("vectorize", lambda: _embed_pages_as_vectors(delta_pages)),
        #("keyword", lambda: _run_fingerprinting(delta_pages)),
        #("map_links", lambda: _find_link_events_for_all_pages()),        # can only be done on all pages, no subsets
        ("find_duplicates", lambda: _find_duplicates()),                      # can only be done on all pages, no subsets
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
    from db.table_utils import create_table
    from pages.schema_table_pages import SCHEMA_PAGES
    from pages.scrape_list_of_available_pages import scrape_page_metadata_in_space
    from pages.scrape_page_htmls import scrape_page_contents_from_server
    from sync.delete_dead_pages import delete_dead_db_pages
    from spaces.space_utils import list_configured_space_ids, get_space_attribute
    # we tuck the module imports inside, so folks skipping scraping have a more responsive application

    create_table("pages", SCHEMA_PAGES)  # this does nothing if the table already exists

    space_ids = list_configured_space_ids()
    delta_pages = []
    all_cloud_ids = []
    for space_id in space_ids:
        space_name = get_space_attribute(space_id, "id", "alias")
        print("-" * WIDTH_NICE)
        print(f"Scraping page metadata for space {space_name.upper()} ({space_id})...\n")
        results = scrape_page_metadata_in_space(space_id, hard_refresh=hard_refresh)

        all_cloud_ids += results['all_cloud_pages']           # store this for later checking of deleted pages

        pids = results["pids"]
        print(f"{DIM}Stored metadata for {RESET}{results['stored_count']}{DIM} pages.\n{RESET}")
        if results['skipped_count'] != 0:
            print(f"{DIM}Skipping {RESET}{results['skipped_count']}{DIM} pages, as they have not changed since your last sync.\n{RESET}")
        elif not hard_refresh:
            print(f"{DIM}Storing {RESET}everything.")
        else:
            print(f"{DIM}Storing {RESET}everything{DIM}, as you chose to {RESET}hard refresh{DIM} your database.{RESET}")

        if results['stored_count'] == 0:
            continue  # skip this space, as nothing has changed
        print(f"{DIM}Now syncing page contents...{RESET}")
        scrape_page_contents_from_server(pids)
        print(f"{DIM}Successfully stored page contents for {RESET}{results['stored_count']}{DIM} pages.{RESET}")

        delta_pages.extend(pids)

    delete_dead_db_pages(all_cloud_ids)
    return delta_pages

# - STEPS ----------------------------------------------
# we split this out here so possibly heavy module loading can be staged
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
def _add_basic_metadata_in_bulk(delta_pages):
    from pages.parsing.basic_metadata_extractor import add_basic_metadata_in_bulk
    add_basic_metadata_in_bulk(delta_pages)
def _clean_link_formatting_and_store_link_list(delta_pages):
    from pages.parsing.link_parser import clean_and_store_links
    clean_and_store_links(delta_pages)
def _extract_excerpt_info(delta_pages):
    from analysis.stats_excerpts import find_and_store_excerpt_info
    find_and_store_excerpt_info(delta_pages)
def _type_all_pages(delta_pages):
    from pages.types.page_typer import type_all_pages
    type_all_pages(delta_pages)
def _scan_for_duplicates():
    from analysis.stats_duplicates import scan_for_duplicates_in_corpus
    scan_for_duplicates_in_corpus()

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


