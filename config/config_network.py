from config.confluence_auth import load_conf_url

API_V2 = "wiki/api/v2/"
API_V1 = "wiki/rest/api/"

CONFLUENCE_BASE_URL = load_conf_url() + API_V2       # as users may have a different confluence instance
CONFLUENCE_BASE_URL_V1 = load_conf_url() + API_V1       # as users may have a different confluence instance
DEFAULT_HEADERS = { "Accept": "application/json" }

ENDPOINT_PAGES = "pages"
ENDPOINT_AUTHORS = "versions"
ENDPOINT_CHILDREN = "direct-children"
ENDPOINT_SPACES = "spaces"

FORMAT_STORAGE = "storage"