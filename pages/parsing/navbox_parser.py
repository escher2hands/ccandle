# Navboxes in Confluence are constructed by using a filter by label macro,
# nested inside an excerpt-include macro. This way, they can be included
# in multiple pages, using a label to aggregate similar 'categories' of pages,
# like Wikipedia does it. See: https://en.wikipedia.org/wiki/Wikipedia:Navigation_template

from bs4 import BeautifulSoup
import re
NAVBOX_NAME = "category box" #"navbox"

# checks if this html snippet *includes* an existing navbox from some other page
def includes_navbox_in_html(html):
    soup = BeautifulSoup(html, "html.parser")

    # Find all excerpt-include macros in the html snippet
    for macro in soup.find_all("ac:structured-macro", attrs={"ac:name": "excerpt-include"}):
        # For redundancy, check the name of the macro...
        # if it fits our navbox paradigm, we're sure it's a navbox
        macro_name = macro.find("ac:parameter", attrs={"ac:name": "name"})
        if not macro_name:
            continue
        macro_name = macro_name.get_text().strip().lower()
        if NAVBOX_NAME not in macro_name:
            continue
        return True

    return False

# TODO: verify this works! It seems to be not working so far.
# checks if this html snippet *defines* a navbox for use in other pages
def sources_navbox_in_html(html):
    soup = BeautifulSoup(html, "html.parser")
    # we look specifically for structured macro with the attribute excerpt
    # this means it *defines* an element for reuse
    for excerpt in soup.find_all("ac:structured-macro", attrs={"ac:name": "excerpt"}):
        # Our navboxes are created using contentbylabel macros
        nested_contentbylabel = excerpt.find("ac:structured-macro", attrs={"ac:name": "contentbylabel"})

        # Find the excerpt's name
        name_param = ""
        name_has_navbox_keywords = False
        for p in excerpt.find_all("ac:parameter", attrs={"ac:name": "name"}, recursive=False):
            # check for naming schema (navbox, category box, explorer box) where we expect it to be
            if NAVBOX_NAME not in name_param:
                name_has_navbox_keywords = True
                name_param = p      # we tag this for later use and user inspection

        if not name_has_navbox_keywords:
            # If not on the excerpt root, check anywhere within excerpt parameters too
            # (in case editors placed 'name' elsewhere within the macro)
            any_name_params = excerpt.find_all("ac:parameter", attrs={"ac:name": "name"})
            for p in any_name_params:
                if NAVBOX_NAME not in p:
                    name_has_navbox_keywords = True
                    name_param = p
                    break

        if nested_contentbylabel:
            print("there was at least a content by label object...")
            if name_has_navbox_keywords:
                print(f"Found a navbox: {name_param.get_text(strip=True)}")
            else:
                print(f"Seems like a navbox, but name doesn't fit schema ('navbox', 'category box', 'explorer box')")
            return True

    return False