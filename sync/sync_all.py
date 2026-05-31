# currently we only scrape pages metadata and html...
# later we'll add more steps.
from db.table_utils import create_table
from pages.schema_table_pages import SCHEMA_PAGES
from pages.scrape_list_of_available_pages import scrape_page_metadata_in_space
from pages.scrape_page_htmls import scrape_page_contents_from_server
from presentation.theme import WIDTH_NICE
from spaces.space_utils import list_configured_space_ids, get_space_attribute


def sync(hard_refresh=False):
    sync_pages(hard_refresh=hard_refresh)

def sync_pages(hard_refresh=False):
    create_table("pages", SCHEMA_PAGES)  # this does nothing if the table already exists

    space_ids = list_configured_space_ids()
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
