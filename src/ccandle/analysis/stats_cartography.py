
from ccandle.config.config_db import PATH_DB, TABLE_PAGES
from ccandle.db.db_query_utils import query_db_results
from collections import deque, defaultdict
import sqlite3, json
from ccandle.db.db_utils import get_field_in_pages


def make_maps(space_id, path_to_db=PATH_DB, limit=20):
    rows = query_db_results(
        "id, child_list, links_list",
        where_clause=f"space_id = {space_id}",
        path_to_db=path_to_db,
    )

    pid_to_info = {}
    incoming_counts = defaultdict(int)

    for pid, child_json, links_json in rows:
        links = json.loads(links_json)
        pid_to_info[pid] = {
            "children": json.loads(child_json),
            "outgoing_links": len(links),
        }

        for target in links:
            target_id = target.partition(":")[2]
            incoming_counts[target_id] += 1

    parent_map = build_parent_map(pid_to_info)
    depth_map = compute_depths(pid_to_info, parent_map)
    subtree_sizes, descendant_map = build_all_subtree_metrics(pid_to_info)

    results = []
    for pid, info in pid_to_info.items():
        children = info["children"]
        outgoing_links = info["outgoing_links"]
        incoming_links = incoming_counts.get(pid, 0)

        if (len(children) > 2 and subtree_sizes.get(pid, 0) > 0) or outgoing_links + incoming_links > 10:
            results.append(
                {
                    "pid": pid,
                    "direct_children": len(children),
                    "descendants": subtree_sizes.get(pid, 0),
                    "outgoing_links": outgoing_links,
                    "incoming_links": incoming_links,
                    "depth": depth_map.get(pid, 0),
                }
            )

    def score(node):
        return (
                node["direct_children"]
                + node["descendants"] * 0.1
                + node["incoming_links"]
                + node["outgoing_links"]
        )
    results.sort(key=score, reverse=True)
    results = results[:limit]

    with sqlite3.connect(path_to_db) as conn:
        trunk_metrics = get_trunk_metrics({r["pid"] for r in results}, conn)
        for result in results:
            desc_ids = descendant_map.get(result["pid"], set())
            placeholders = ",".join(["?"] * len(desc_ids))
            ids = tuple(desc_ids)

            result["avg_word_count"] = round(conn.execute(
                f"SELECT AVG(word_count) FROM {TABLE_PAGES} WHERE id IN ({placeholders})", ids
            ).fetchone()[0] or 0, -1)
            result['subtree_words'] = result['avg_word_count'] * result['descendants']

            result["word_count"] = get_field_in_pages(result['pid'], "word_count")
            result["type"] = get_field_in_pages(result['pid'], "page_type")
            result["most_common_type"] = (conn.execute(
                f"SELECT page_type FROM {TABLE_PAGES} WHERE id IN ({placeholders}) AND page_type IS NOT NULL "
                f"GROUP BY page_type ORDER BY COUNT(*) DESC LIMIT 1", ids
            ).fetchone() or (None,))[0]

            metrics = trunk_metrics.get(result["pid"], {})
            result["title"] = metrics.get("title")
            result["last_modified"] = metrics.get("last_modified")

    return results

def build_parent_map(pid_to_info):
    return {
        child: parent
        for parent, info in pid_to_info.items()
        for child in info["children"]
    }

def compute_depths(pid_to_info, parent_map):
    all_nodes = set(pid_to_info.keys())

    for info in pid_to_info.values():
        all_nodes.update(info["children"])

    roots = [n for n in all_nodes if n not in parent_map]
    depth = {r: 0 for r in roots}
    q = deque(roots)

    while q:
        node = q.popleft()
        node_depth = depth[node]

        children = pid_to_info.get(node, {}).get("children", [])
        for child in children:
            if child not in depth or node_depth + 1 < depth[child]:
                depth[child] = node_depth + 1
                q.append(child)

    return depth

def build_all_subtree_metrics(pid_to_info):
    subtree_size = {}
    descendant_set = {}

    for node in pid_to_info:
        if node not in subtree_size:
            compute_subtree_metrics(
                node,
                pid_to_info,
                subtree_size,
                descendant_set,
            )

    return subtree_size, descendant_set

def compute_subtree_metrics(node, pid_to_info, subtree_size, descendant_set):
    children = pid_to_info.get(node, {}).get("children", [])
    all_descendants = set()

    for child in children:
        all_descendants.add(child)
        child_descendants = compute_subtree_metrics(
            child,
            pid_to_info,
            subtree_size,
            descendant_set,
        )
        all_descendants.update(child_descendants)

    subtree_size[node] = len(all_descendants)
    descendant_set[node] = all_descendants

    return all_descendants

def get_trunk_metrics(pids, conn):
    placeholders = ",".join(["?"] * len(pids))
    rows = conn.execute(
        f"SELECT id, title, last_modified FROM {TABLE_PAGES} WHERE id IN ({placeholders})",
        tuple(pids)
    ).fetchall()
    return {row[0]: {"title": row[1], "last_modified": row[2]} for row in rows}

def interpret_depth(depth):
    if depth == 0:      interpretation = "root"
    elif depth <= 1:    interpretation = "top level"
    elif depth <= 3:    interpretation = "mid"
    else:               interpretation = "deep"
    return interpretation + " " * (10-len(interpretation)) + f" ({depth})"

def get_descendants(space_id, page_id, path_to_db=PATH_DB):
    rows = query_db_results("id, child_list", where_clause=f"space_id = {space_id}", path_to_db=path_to_db)
    pid_to_child_list_map = {pid: json.loads(child_list_json) for pid, child_list_json in rows}

    parent_map = build_parent_map(pid_to_child_list_map)
    depth_map = compute_depths(pid_to_child_list_map, parent_map)
    _, descendant_map = build_all_subtree_metrics(pid_to_child_list_map)

    desc_ids = descendant_map.get(page_id, set())
    if not desc_ids:
        return []

    base_depth = depth_map.get(page_id, 0)

    with sqlite3.connect(path_to_db) as conn:
        trunk_metrics = get_trunk_metrics(desc_ids, conn)

    return sorted(
        [
            {
                "pid": pid,
                "title": trunk_metrics.get(pid, {}).get("title"),
                "depth": depth_map.get(pid, base_depth) - base_depth,
            }
            for pid in desc_ids
        ],
        key=lambda x: (x["depth"], x["title"] or ""),
    )
