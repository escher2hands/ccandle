from config.config_app import APP_NAME
from platformdirs import user_data_dir
from pathlib import Path

TABLE_PAGES = "pages"
TABLE_LABELS = "labels"
TABLE_AUTHORS = "authors"
TABLE_VECTORS = "vectors"

DATA_DIR = Path(user_data_dir(APP_NAME))
DB_DIR = DATA_DIR / "db"
CONFIG_DIR = DATA_DIR / "config"

PATH_DB = DB_DIR / "confluence_mirror.db"

for directory in (DB_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)
