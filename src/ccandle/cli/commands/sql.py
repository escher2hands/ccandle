def register(subparsers):
    p = subparsers.add_parser("sql", help="Query your local pages db directly")
    sql_sub = p.add_subparsers(dest="sql_cmd")

    query_p = sql_sub.add_parser("query", help="Run a SQL query against your local pages db")
    query_p.add_argument("query", help="Your SQL query string")
    query_p.add_argument("--force-table", action="store_true", help="Force table view, truncating lengthy values")

    sql_sub.add_parser("columns", help="List the columns in your local pages table")
    p.set_defaults(sql_cmd="query")


def run(args):
    from ccandle.analysis.sql_queries import query_via_cli, get_column_names
    if args.sql_cmd == "columns":
        columns = get_column_names()
        for column in columns:
            print(column)
        return 0
    return query_via_cli(args.query, force_table=args.force_table)