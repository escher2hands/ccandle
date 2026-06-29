from config.confluence_auth import load_conf_url

API_V2 = "wiki/api/v2/"
API_V1 = "wiki/rest/api/"

user_input_url = load_conf_url().rstrip('/') + '/'      # guard against issues with trailing slash
CONFLUENCE_BASE_URL = user_input_url + API_V2
CONFLUENCE_BASE_URL_V1 = user_input_url + API_V1
DEFAULT_HEADERS = { "Accept": "application/json" }

ENDPOINT_PAGES = "pages"
ENDPOINT_AUTHORS = "versions"
ENDPOINT_CHILDREN = "direct-children"
ENDPOINT_SPACES = "spaces"

FORMAT_STORAGE = "storage"