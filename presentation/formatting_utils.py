
# truncate with ellipses
def cut(your_string, length, padding=0):
    truncated = your_string
    if length > 0 and len(your_string) > length:
        truncated = your_string[:length-3]
        truncated = truncated + "..."

    if length > 0 and truncated == your_string:
        truncated = truncated.ljust(length)

    if padding > 0:
        truncated = truncated + " " * padding

    return truncated


# parse lists of pids from the terminal. Usually raw numbers,
# sometimes comma separated, sometimes space separated.
# returns them as a neat list of pids.
def parse_pids_from_terminal(raw_id_input):
    parts = [
        part.strip()
        for item in raw_id_input
        for part in item.split(",")
        if part.strip()
    ]
    for p in parts:
        if not p.isdigit():
            raise ValueError(f"Invalid page ID: {p}")
    return parts