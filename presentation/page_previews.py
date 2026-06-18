import shutil

def get_pages_preview(pids, *fields):
    from db.db_query_utils import query_field_multi_in_pages
    results = []
    for pid in pids:
        values = query_field_multi_in_pages(pid, *fields)
        result = {"id": pid, **dict(zip(fields, values))}
        results.append(result)
    return results

def render_table(results, columns):
    from presentation.theme import DIM, RESET, BOLD

    if not results:
        print("No results.")
        return

    def format_cell(val, width, align_left=True):
        val = "" if val is None else str(val)
        if width:
            val = val[:width - 1] + "…" if len(val) > width else val
            return f"{val:<{width}}" if align_left else f"{val:>{width}}"
        return val

    def natural_width(col):
        header_w = len(col["label"])
        data_w = max((len(str(row.get(col["key"], "") or "")) for row in results), default=0)
        return max(header_w, data_w)

    widths = [col.get("width") or natural_width(col) for col in columns]
    sep = f"{DIM}" + "-+-".join("-" * w for w in widths) + f"{RESET}"
    headers = [format_cell(col["label"], w) for col, w in zip(columns, widths)]
    print(f" {DIM}|{RESET} ".join(f"{BOLD}{h}{RESET}" for h in headers))
    print(sep)
    for row in results:
        cells = [format_cell(row.get(col["key"]), w) for col, w in zip(columns, widths)]
        print(f" {DIM}|{RESET} ".join(cells))

def render_list(results, columns):
    from presentation.theme import DIM, RESET, BOLD
    sep = f"{DIM}" + "-" * shutil.get_terminal_size().columns + f"{RESET}"
    for row in results:
        print(sep)
        for col in columns:
            label = f"{BOLD}{col['label']}{RESET}"
            value = str(row.get(col["key"], "") or "")
            print(f"{label}: {value}")
    print(sep)

def render_table_forced(results, columns):
    from presentation.theme import DIM, RESET, BOLD
    import shutil

    if not results:
        print("No results.")
        return

    def natural_width(col):
        header_w = len(col["label"])
        data_w = max((len(str(row.get(col["key"], "") or "")) for row in results), default=0)
        return max(header_w, data_w)

    terminal_w = shutil.get_terminal_size().columns
    separator_overhead = (len(columns) - 1) * 3
    fair_share = (terminal_w - separator_overhead) // len(columns)
    widths = [min(natural_width(col), fair_share) for col in columns]

    def format_cell(val, width):
        val = "" if val is None else str(val)
        val = val[:width - 1] + "…" if len(val) > width else val
        return f"{val:<{width}}"

    sep = f"{DIM}" + "-+-".join("-" * w for w in widths) + f"{RESET}"
    headers = [format_cell(col["label"], w) for col, w in zip(columns, widths)]
    print(f" {DIM}|{RESET} ".join(f"{BOLD}{h}{RESET}" for h in headers))
    print(sep)
    for row in results:
        cells = [format_cell(row.get(col["key"]), w) for col, w in zip(columns, widths)]
        print(f" {DIM}|{RESET} ".join(cells))


def render_results(results, columns, force_table=False):
    import shutil

    def natural_width(col):
        header_w = len(col["label"])
        data_w = max((len(str(row.get(col["key"], "") or "")) for row in results), default=0)
        return max(header_w, data_w)

    if not results:
        print("No results.")
        return

    if force_table:
        render_table_forced(results, columns)
        return

    total_width = sum(natural_width(col) for col in columns) + (len(columns) - 1) * 3
    if total_width > shutil.get_terminal_size().columns:
        render_list(results, columns)
    else:
        render_table(results, columns)