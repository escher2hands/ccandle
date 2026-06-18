# Walk the content in DOM order, collecting <p> tags as paragraph anchors
# and rolling up any immediately-following list content into them.
HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
LIST_TAGS    = {"ul", "ol"}
SKIP_TAGS    = {"ac:adf-extension", "ac:image", "ac:structured-macro",
                "figure", "table", "nav", "header", "footer", "aside"}

def extract_prose_paragraphs(soup, return_text=False):
    def get_words(tag):
        return tag.get_text(separator=' ', strip=True).split()

    def is_inside_list(tag):
        for parent in tag.parents:
            if parent.name in LIST_TAGS:
                return True
        return False

    def is_inside_adf_fallback(tag):
        for parent in tag.parents:
            if parent.name == "ac:adf-fallback":
                return True
        return False

    def is_structural_only(p_tag):
        text = p_tag.get_text(strip=True)
        if not text or len(text.split()) < 2:
            return True
        if p_tag.find("ac:image") or p_tag.find("ac:structured-macro"):
            if len(text.split()) < 5:
                return True
        return False

    def process_children(children):
        results = []
        i = 0
        while i < len(children):
            tag = children[i]

            if tag.name in SKIP_TAGS or tag.name in HEADING_TAGS:
                i += 1
                continue

            if tag.name == "p":
                if is_structural_only(tag) or is_inside_list(tag) or is_inside_adf_fallback(tag):
                    i += 1
                    continue

                words = get_words(tag)

                j = i + 1
                while j < len(children):
                    sibling = children[j]
                    if sibling.name in LIST_TAGS and not is_inside_adf_fallback(sibling):
                        words += get_words(sibling)
                        j += 1
                    else:
                        break

                if words:
                    results.append(' '.join(words) if return_text else len(words))
                i = j
                continue

            if tag.name in LIST_TAGS:
                if not is_inside_adf_fallback(tag):
                    words = get_words(tag)
                    if words:
                        results.append(' '.join(words) if return_text else len(words))
                i += 1
                continue

            i += 1
        return results

    def get_flat_children(parent):
        return [c for c in parent.children
                if hasattr(c, "name") and c.name is not None]

    layout_cells = soup.find_all("ac:layout-cell")
    if layout_cells:
        results = []
        for cell in layout_cells:
            results += process_children(get_flat_children(cell))
        return results
    else:
        return process_children(get_flat_children(soup))


def extract_lead_paragraph_from_soup(soup):
    def is_inside_list(tag):
        for parent in tag.parents:
            if parent.name in LIST_TAGS:
                return True
        return False

    def is_inside_adf_fallback(tag):
        for parent in tag.parents:
            if parent.name == "ac:adf-fallback":
                return True
        return False

    def is_structural_only(p_tag):
        text = p_tag.get_text(strip=True)
        if not text or len(text.split()) < 2:
            return True
        if p_tag.find("ac:image") or p_tag.find("ac:structured-macro"):
            if len(text.split()) < 5:
                return True
        return False

    def find_lead(children):
        i = 0
        while i < len(children):
            tag = children[i]

            if tag.name in SKIP_TAGS or tag.name in HEADING_TAGS:
                i += 1
                continue

            if tag.name == "p":
                if is_structural_only(tag) or is_inside_list(tag) or is_inside_adf_fallback(tag):
                    i += 1
                    continue

                rolled = [tag]
                j = i + 1
                while j < len(children):
                    sibling = children[j]
                    if sibling.name in LIST_TAGS and not is_inside_adf_fallback(sibling):
                        rolled.append(sibling)
                        j += 1
                    else:
                        break

                return rolled

            if tag.name in LIST_TAGS:
                if not is_inside_adf_fallback(tag):
                    return [tag]
                i += 1
                continue

            i += 1
        return None

    def get_flat_children(parent):
        return [c for c in parent.children
                if hasattr(c, "name") and c.name is not None]

    layout_cells = soup.find_all("ac:layout-cell")
    if layout_cells:
        for cell in layout_cells:
            result = find_lead(get_flat_children(cell))
            if result:
                break
        else:
            result = None
    else:
        result = find_lead(get_flat_children(soup))

    if result is None:
        return None

    return ''.join(str(tag) for tag in result)