from config.config_db import PATH_DB
import sqlite3

def create_table(table_name, table_schema):
    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} ({table_schema})""")
    conn.commit()
    conn.close()

def create_table_hard(table_name, table_schema):
    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    cur.execute(f"""DROP TABLE IF EXISTS {table_name}""")
    cur.execute(f"""CREATE TABLE IF NOT EXISTS {table_name} ({table_schema})""")
    conn.commit()
    conn.close()

def drop_table(table_name):
    conn = sqlite3.connect(PATH_DB)
    cur = conn.cursor()
    cur.execute(f"""DROP TABLE IF EXISTS {table_name}""")
    conn.commit()
    conn.close()