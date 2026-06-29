from config.config_db import PATH_DB, TABLE_PAGES
from db.db_query_utils import query_db_results
from collections import deque
import sqlite3, json

def make_maps(space_id, path_to_db=PATH_DB, limit=20):
    rows = query_db_results("id, child_list", where_clause=f"space_id = {space_id}", path_to_db=path_to_db)
    pid_to_child_list_map = {pid: json.loads(child_list_json) for pid, child_list_json in rows}

    parent_map = build_parent_map(pid_to_child_list_map)
    depth_map = compute_depths(pid_to_child_list_map, parent_map)
    subtree_sizes, descendant_map = build_all_subtree_metrics(pid_to_child_list_map)

    results = [
        {
            "pid": pid,
            "direct_children": len(children),
            "descendants": subtree_sizes.get(pid, 0),
            "depth": interpret_depth(depth_map.get(pid, 0)),
        }
        for pid, children in pid_to_child_list_map.items()
        if len(children) > 2 and subtree_sizes.get(pid, 0) > 0
    ]

    results.sort(key=lambda x: x["descendants"], reverse=True)
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

            result["most_common_type"] = (conn.execute(
                f"SELECT page_type FROM {TABLE_PAGES} WHERE id IN ({placeholders}) AND page_type IS NOT NULL "
                f"GROUP BY page_type ORDER BY COUNT(*) DESC LIMIT 1", ids
            ).fetchone() or (None,))[0]

            metrics = trunk_metrics.get(result["pid"], {})
            result["title"] = metrics.get("title")
            result["last_modified"] = metrics.get("last_modified")

    return results

def build_parent_map(pid_to_child_list_map):
    parent_map = {
        child: parent
        for parent, children in pid_to_child_list_map.items()
        for child in children
    }
    return parent_map

def compute_depths(pid_to_child_list_map, parent_map):
    all_nodes = set(pid_to_child_list_map.keys())
    for children in pid_to_child_list_map.values():
        all_nodes.update(children)

    roots = [n for n in all_nodes if n not in parent_map]
    depth = {r: 0 for r in roots}
    q = deque(roots)

    while q:
        node = q.popleft()
        node_depth = depth[node]
        for child in pid_to_child_list_map.get(node, []):
            if child not in depth or node_depth + 1 < depth[child]: # only set if not already set or if we find a shorter path
                depth[child] = node_depth + 1
                q.append(child)

    return depth

def build_all_subtree_metrics(pid_to_child_list_map):
    subtree_size = {}
    descendant_set = {}

    for node in pid_to_child_list_map:
        if node not in subtree_size:
            compute_subtree_metrics(node, pid_to_child_list_map, subtree_size, descendant_set)

    return subtree_size, descendant_set

def compute_subtree_metrics(node, pid_to_child_list_map, subtree_size, descendant_set):
    children = pid_to_child_list_map.get(node, [])
    all_descendants = set()

    for child in children:
        all_descendants.add(child)
        child_descendants = compute_subtree_metrics(child, pid_to_child_list_map, subtree_size, descendant_set)
        all_descendants.update(child_descendants)

    subtree_size[node] = len(all_descendants)
    descendant_set[node] = all_descendants
    return all_descendants

def get_descendant_metrics(desc_ids, conn):
    placeholders = ",".join(["?"] * len(desc_ids))
    ids = tuple(desc_ids)

    avg_word_count = conn.execute(
        f"SELECT AVG(word_count) FROM {TABLE_PAGES} WHERE id IN ({placeholders})", ids
    ).fetchone()[0] or 0

    most_common_type = conn.execute(
        f"SELECT page_type FROM {TABLE_PAGES} WHERE id IN ({placeholders}) AND page_type IS NOT NULL "
        f"GROUP BY page_type ORDER BY COUNT(*) DESC LIMIT 1", ids
    ).fetchone()
    most_common_type = most_common_type[0] if most_common_type else None
    return avg_word_count, most_common_type


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

