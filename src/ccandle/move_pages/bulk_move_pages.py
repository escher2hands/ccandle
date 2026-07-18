from ccandle.network.network_utils import request_move_page


def bulk_move_pages(target_id, page_ids, dry_run=False, quiet=False):
    """Move a batch of pages under target_id. Continues past individual failures."""
    results = []
    for page_id in page_ids:
        if dry_run:
            if not quiet:
                print(f"[dry-run] Would move page {page_id} -> parent {target_id}")
            results.append({"status": "dry-run", "page_id": page_id, "target_id": target_id})
            continue

        result = request_move_page(page_id, target_id)
        results.append(result)

        if not quiet:
            if result["status"] == "success":
                print(f"Moved page {page_id} -> parent {target_id}")
            else:
                print(f"FAILED page {page_id}: {result['status']} ({result['http_status']})")

    succeeded = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] not in ("success", "dry-run"))

    if not quiet:
        print(f"\nDone. {succeeded} succeeded, {failed} failed, {len(results)} total.")

    return {"succeeded": succeeded, "failed": failed, "total": len(results), "results": results}