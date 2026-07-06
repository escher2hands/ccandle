
from bs4 import BeautifulSoup
from ccandle.db.db_query_utils import query_field_in_pages
from ccandle.pages.parsing.excerpt_defs import *
from ccandle.pages.parsing.link_parser import resolve_pid_from_title_and_space
from ccandle.spaces.space_utils import get_space_attribute
import re, json
import secrets
import uuid

EXCERPT_INCLUDE_MACRO_RE = re.compile(
    r"<ac:structured-macro[^>]*ac:name=\"excerpt-include\".*?</ac:structured-macro>",
    re.DOTALL
)
WRAPPED_MACRO_RE = re.compile(
    r"<p[^>]*>\s*"
    r"<ac:structured-macro[^>]*ac:name=\"excerpt-include\".*?</ac:structured-macro>\s*"
    r"</p>",
    re.DOTALL
)
EXCERPT_INCLUDE_TEMPLATE = """
<p local-id="{paragraph_id}">
<ac:structured-macro
    ac:name="excerpt-include"
    ac:schema-version="1"
    ac:local-id="{local_id}"
    ac:macro-id="{macro_id}">
<ac:parameter ac:name="">
<ac:link>
<ri:page{space}
ri:content-title="{title}"
ri:version-at-save="{version}" />
</ac:link>
</ac:parameter>
<ac:parameter ac:name="name">{excerpt_name}</ac:parameter>
<ac:parameter ac:name="nopanel">true</ac:parameter>
</ac:structured-macro>
</p>
""".strip()

# Analyze the HTML to see if it contains an excerpt macro with
# a nested contentbylabel macro
# if it has a name, we check this so it can be double checked later.
def find_excerpt_sources_in_html(html):
    soup = BeautifulSoup(html, "html.parser")
    excerpts = []
    for excerpt in soup.find_all("ac:structured-macro", attrs={"ac:name": "excerpt"}):
        name_param = excerpt.find("ac:parameter", attrs={"ac:name": "name"})
        name_text = name_param.get_text(strip=True) if name_param else "UNNAMED"
        nested_contentbylabel = excerpt.find(
            "ac:structured-macro", attrs={"ac:name": "contentbylabel"}
        )
        if nested_contentbylabel:       # a navbox pattern!
            # It structurally IS a navbox. Log the name for usability
            excerpts.append({
                'type': NAVBOX_FLAG,
                'name': _normalize_name(name_text),
                'is_source': SOURCE_FLAG,
                'unnormalized_name': name_text,
            })
        else:
            excerpts.append({
                'type': EXCERPT_FLAG,
                'name': _normalize_name(name_text),
                'is_source': SOURCE_FLAG,
                'unnormalized_name': name_text,
            })
    return excerpts

def find_excerpt_includes_in_html(html, my_space_id, existing_excerpt_index):
    soup = BeautifulSoup(html, "html.parser")
    excerpt_includes = []

    for excerpt in soup.find_all(
        "ac:structured-macro",
        attrs={"ac:name": "excerpt-include"}
    ):
        # Find the referenced page
        page_tag = excerpt.find("ri:page")
        if not page_tag:
            continue

        extracted_source_title = page_tag.get("ri:content-title")
        my_space_shid = get_space_attribute(my_space_id, "id", "short_id")
        space_short_id = page_tag.get("ri:space-key", my_space_shid)
        # Find the excerpt name parameter (if present)
        name_param = excerpt.find(
            "ac:parameter",
            attrs={"ac:name": "name"}
        )

        extracted_excerpt_name = (
            name_param.get_text(strip=True)
            if name_param
            else None
        )
        source_page = resolve_pid_from_title_and_space(extracted_source_title, space_short_id)
        source_id = source_page['target_pid']
        name = _normalize_name(extracted_excerpt_name)
        excerpt_includes.append({
            "type": _navbox_or_excerpt(str(source_id), name, existing_excerpt_index),
            "name": name,
            "is_source": CONSUMER_FLAG,
            "source_id": source_id,
        })

    return excerpt_includes

def _navbox_or_excerpt(source_id, excerpt_name, existing_excerpt_sources_index):
    items = existing_excerpt_sources_index.get(source_id, [])
    for e in items:
        if e["name"] == excerpt_name:
            return e['type']
    return EXCERPT_FLAG

def _normalize_name(text):
    if text is None:
        return None
    text = text.lower()
    return str(text).replace('"', '').replace("'", "").replace(":", "")

def serialize_excerpt(excerpt):
    return f"{excerpt['type']}:{excerpt['name']}:{excerpt['is_source']}:{excerpt['source_id']}"
def deserialize_excerpt(serialized_excerpt):
    EXCERPT_RE = re.compile(r"^([^:]+):([^:]+):([^:]+):([^:]+)$")
    match = EXCERPT_RE.match(serialized_excerpt)

    if match:
        exc_type, name, is_source, source_id = match.groups()
        return {
            'type': exc_type,
            'name': name,
            'is_source': is_source,
            'source_id': source_id,
        }
    return None

def serialize_loaded_excerpts(excerpt_data):
    serialized = {}
    for pid, exc_items in excerpt_data.items():
        serialized[pid] = [serialize_excerpt(exc) for exc in exc_items]
    return serialized


# Removes all excerpt-include macros from Confluence storage HTML.
def strip_excerpt_includes(your_html):
    # First remove wrapped versions (your insertion format)
    html = WRAPPED_MACRO_RE.sub("", your_html)

    # Then remove any remaining standalone macros
    html = EXCERPT_INCLUDE_MACRO_RE.sub("", html)
    # diff = html.replace(your_html, '')
    # print(diff)
    return html

def page_already_has_an_excerpt_include(pid, navbox_only=False):
    excerpts_list = query_field_in_pages(pid, 'excerpts')
    if not excerpts_list:
        return None
    for serialized_excerpt in json.loads(excerpts_list):
        excerpt = deserialize_excerpt(serialized_excerpt)
        if excerpt['type'] == NAVBOX_FLAG:      # pages should have at most one navbox.
            return excerpt
        if not navbox_only and excerpt['is_source'] == CONSUMER_FLAG:
            return excerpt

    return None

def build_excerpt_include_macro_from_source_and_page_info(excerpt_source, target_page):
    space = ""

    if excerpt_source["space_key"] != target_page["space_key"]:
        space = f' ri:space-key="{excerpt_source["space_key"]}"'

    return EXCERPT_INCLUDE_TEMPLATE.format(
        paragraph_id=secrets.token_hex(6),
        local_id=str(uuid.uuid4()),
        macro_id=str(uuid.uuid4()),
        space=space,
        title=excerpt_source["title"],
        version=excerpt_source["version"],
        excerpt_name=excerpt_source["name"],
    )

