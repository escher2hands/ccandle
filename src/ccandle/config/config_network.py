from ccandle.config.confluence_auth import load_conf_url

API_V2 = "wiki/api/v2/"
API_V1 = "wiki/rest/api/"

def get_confluence_base_url():
    user_input_url = load_conf_url().rstrip('/') + '/' # guard against issues with trailing slash
    return user_input_url + API_V2
def get_confluence_base_url_v1():
    user_input_url = load_conf_url().rstrip('/') + '/' # guard against issues with trailing slash
    return user_input_url + API_V1

DEFAULT_HEADERS = { "Accept": "application/json" }

ENDPOINT_PAGES = "pages"
ENDPOINT_AUTHORS = "versions"
ENDPOINT_CHILDREN = "direct-children"
ENDPOINT_SPACES = "spaces"

FORMAT_STORAGE = "storage"