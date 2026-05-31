
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
    import shutil
    if not results:
        print("No results.")
        return

    def format_cell(val, width, align_left=True):
        val = "" if val is None else str(val)
        if width:
            val = val[:width - 1] + "…" if len(val) > width else val
            return f"{val:<{width}}" if align_left else f"{val:>{width}}"
        return val

    explicit_widths = [col.get("width") for col in columns]
    bounded_total = sum(w for w in explicit_widths if w) + (len(columns) - 1) * 3
    default_width = shutil.get_terminal_size().columns - bounded_total
    widths = [w or default_width for w in explicit_widths]

    sep = f"{DIM}" + "-+-".join("-" * w for w in widths) + f"{RESET}"

    headers = [format_cell(col["label"], w) for col, w in zip(columns, widths)]
    print(f" {DIM}|{RESET} ".join(f"{BOLD}{h}{RESET}" for h in headers))
    print(sep)

    for row in results:
        cells = [format_cell(row.get(col["key"]), w) for col, w in zip(columns, widths)]
        print(f" {DIM}|{RESET} ".join(cells))