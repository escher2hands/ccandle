# goal here is to derive the plain text of a Confluence page, using its HTML.
# we add a bit of value beyond just stripping with beautiful soup:
# - headings
# - links in line
# - bullet points should be respected
from bs4 import BeautifulSoup
import re

def extract_plain_text_from_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    plain_text = soup.get_text()
    return plain_text

def get_link_count_from_html(html):
    LINK_RE = re.compile(r'<a[^>]*href=\"([^"]+)\"[^>]*>')
    links = re.findall(LINK_RE, html)
    return len(links)

# count the num images inside a given html snippet (usually a whole page)
def get_image_count_from_html(html):
    IMAGE_TAG = "</ac:image>"
    return html.count(IMAGE_TAG)

# count num paragraphs in an html snippet
def get_paragraph_count_from_html(html):
    soup = BeautifulSoup(html, "html.parser")
    # <p> should be our paragraph tag, but we want to skip those inside of tables and image captions
    valid_paragraphs = [
        para_tag for para_tag in soup.find_all("p")
        if not para_tag.find_parent(["table", "ac:caption"])
    ]
    return len(valid_paragraphs)

# finds if there is a link tree macro in the html snippet
def has_link_tree_in_html(html):
    children_macro = re.escape('<ac:structured-macro ac:name=\"children\"')
    children_link_list = re.findall(children_macro, html)
    return len(children_link_list) > 0
