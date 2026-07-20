
from ccandle.presentation.theme import *
from ccandle.spaces.space_utils import display_friendly_space_info
from ccandle.overview.generate_space_overview import STATS_GROUPS, STATS_KEYS, STATS_GROUP_TITLES, share

META_STATS_FIELDS = [
    ("Total pages in space", "total_pages"),
    ("Total words in space", "total_words"),
    ("Total content pages in space", "content_pages"),
    ("Total words in content pages", "content_words"),
]


def print_space_overview(space_data_sets, quiet=False):
    for sdata in space_data_sets:
        print_space_header(sdata['space_id'])
        print()

        sstats = sdata['stats']
        print_meta(sstats, format_value=lambda k, v: str(v))
        print()

        print_grouped(sstats, quiet, lambda k, cfg, v: (
                f"{v * 100:5.1f} %" + (f" | goal: {cfg.goal:5.1f}" if cfg.goal is not None else "")
        ))
        print()

        print_type_header()
        print_page_types(page_types_data=sdata['page_types'], total_pages=sstats['total_pages'])
        print("\n")

"""
def print_space_overview(space_data_sets, quiet=False):
    for sdata in space_data_sets:
        print_space_header(sdata['space_id'])
        print()

        sstats = sdata['stats']
        print_meta(sstats)
        print()

        print_grouped_stats(sstats, quiet=quiet)
        print()

        print(f"PAGE TYPE BREAKDOWN")
        print("-" * WIDTH_NICE)
        print_page_types(page_types_data=sdata['page_types'], total_pages=sstats['total_pages'])
        print("\n")
"""
# format_value(key, cfg, value) -> the string to show for that stat
def print_grouped(stats_dict, quiet, format_value):
    for group in STATS_GROUPS:
        items = [(key, cfg) for key, cfg in STATS_KEYS.items() if cfg.group == group]
        if not items:
            continue

        print(f"\n{STATS_GROUP_TITLES[group]}")
        print("-" * WIDTH_NICE)

        for key, cfg in items:
            value = stats_dict.get(key)
            if value is None:
                continue
            line = f"{cfg.title:<27}: {format_value(key, cfg, value):>16}"
            if not quiet and cfg.hint:
                line += f"  {DIM}→ {cfg.hint}{RESET}"
            print(line)

def print_grouped_stats(space_stats, quiet=False):
    def format_value(key, cfg, value):
        s = f"{value * 100:5.1f} %"
        if cfg.goal is not None:
            s += f" | goal: {cfg.goal:5.1f}"
        return s
    print_grouped(space_stats, quiet, format_value)

def print_meta(stats_dict, format_value):
    for label, key in META_STATS_FIELDS[:2]:
        value = stats_dict.get(key)
        print(f"{label:<30}:{format_value(key, value):>12}")
    print()
    for label, key in META_STATS_FIELDS[2:]:
        value = stats_dict.get(key)
        print(f"{label:<30}:{format_value(key, value):>12}")


def print_page_types(page_types_data, total_pages):
    for p_type, count in page_types_data.items():
        t_share = share(count, total_pages) * 100
        print(f"{t_share:2.0f} %    ({count:5} pages)    {p_type}")

def print_space_header(space_id):
    space_info = display_friendly_space_info(space_id, color=True, long=True) if space_id else "ALL CONFIGURED SPACES"
    print(f'{BLUE}' + '=' * WIDTH_NICE + f'{RESET}')
    print(f"{BOLD}OVERVIEW FOR SPACE {RESET}{space_info}:")

def print_type_header():
    print(f"PAGE TYPE BREAKDOWN")
    print("-" * WIDTH_NICE)
