from config.confluence_auth import load_conf_url

CONFLUENCE_BASE_URL = load_conf_url()       # as users may have a different confluence instance
DEFAULT_HEADERS = { "Accept": "application/json" }

ENDPOINT_PAGES = "pages"
ENDPOINT_AUTHORS = "versions"
ENDPOINT_CHILDREN = "direct-children"
ENDPOINT_SPACES = "spaces"

FORMAT_STORAGE = "storage"