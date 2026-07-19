from ccandle.config.config_db import PATH_DB
import sqlite3

def create_table(table_name, table_schema, path_to_db=PATH_DB):
    conn = sqlite3.connect(path_to_db)
    cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} ({table_schema})""")
    conn.commit()
    conn.close()

def create_table_hard(table_name, table_schema, path_to_db=PATH_DB):
    conn = sqlite3.connect(path_to_db)
    cur = conn.cursor()
    cur.execute(f"""DROP TABLE IF EXISTS {table_name}""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} ({table_schema})""")
    conn.commit()
    conn.close()

def drop_table(table_name, path_to_db=PATH_DB):
    conn = sqlite3.connect(path_to_db)
    cur = conn.cursor()
    cur.execute(f"""DROP TABLE IF EXISTS {table_name}""")
    conn.commit()
    conn.close()