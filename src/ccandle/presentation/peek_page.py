from ccandle.db.db_query_utils import query_field_multi_in_pages
from ccandle.spaces.space_utils import get_space_attribute
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.console import Group
from rich.align import Align
import textwrap

PREVIEW_WIDTH = 80
PREVIEW_MAX_LINES = 20


def panel_page_preview(pid, width=PREVIEW_WIDTH, max_lines=PREVIEW_MAX_LINES) -> Panel:
    title, space_id, link_count, image_count, word_count, plain_text = query_field_multi_in_pages(
        pid, "title", "space_id", "link_count", "image_count", "word_count", "plain_text")

    snippet = trim_snippet(plain_text, width, max_lines)

    metadata = Table.grid(padding=(0, 2))
    metadata.add_row(
        info_chunk("space", get_space_attribute(space_id, 'id', 'alias')),
        info_chunk("links", link_count),
        info_chunk("images", image_count),
        info_chunk("words", word_count),
    )

    title_length_max = width - 10       # force some padding to title
    page = Panel(Text(snippet), title=Text(title[:title_length_max], style="bold"), padding=(1, 1))
    panel_content = Group(Align.center(metadata), page)

    return Panel(panel_content, title=f"previewing: {pid}", border_style="bright_black")

def info_chunk(label, value) -> Text:
    return Text.assemble((label + ": ", "dim"), (str(value), "dim"))

def trim_snippet(text, width=PREVIEW_WIDTH, max_lines=PREVIEW_MAX_LINES) -> str:
    out_lines: list[str] = []
    truncated = False
    width = width -8      # account for panel in panel borders

    for para in text.split("\n"):
        wrapped = textwrap.wrap(para, width=width) or [""]  # preserve blank lines
        remaining = max_lines - len(out_lines)

        if remaining <= 0:
            truncated = True
            break
        if len(wrapped) > remaining:
            out_lines.extend(wrapped[:remaining])
            truncated = True
            break

        out_lines.extend(wrapped)
    else:
        truncated = False  # exhausted all paragraphs within budget

    snippet = "\n".join(out_lines)
    if truncated:
        snippet += "---\n..."
    return snippet