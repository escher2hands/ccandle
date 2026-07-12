# Preview pages in your corpus, without needing to open the browser.
from ccandle.presentation.peek_page import PREVIEW_MAX_LINES, PREVIEW_WIDTH

def register(subparsers):
    p = subparsers.add_parser("preview", help="Peek at a page's contents without going to your web browser")

    p.add_argument("page_id", help="Specify the page ID to preview")
    p.add_argument("--lines", "-l", type=int, default=PREVIEW_MAX_LINES, help="Set the preview length in lines")

def run(args):
    from ccandle.presentation.peek_page import panel_page_preview
    from ccandle.presentation.user_communication import exit_if_not_all_ids_are_in_db
    from rich.console import Console
    console = Console(width=PREVIEW_WIDTH)

    exit_if_not_all_ids_are_in_db([args.page_id])
    preview = panel_page_preview(args.page_id, width=PREVIEW_WIDTH, max_lines=args.lines)
    console.print(preview)
    return 0
