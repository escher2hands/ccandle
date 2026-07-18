from ccandle.config.config_app import APP_NAME
from platformdirs import user_data_dir
from pathlib import Path

TABLE_PAGES = "pages"
TABLE_LABELS = "labels"
TABLE_AUTHORS = "authors"
TABLE_VECTORS = "vectors"
TABLE_LIST = [TABLE_PAGES, TABLE_LABELS, TABLE_AUTHORS, TABLE_VECTORS]

DATA_DIR = Path(user_data_dir(APP_NAME))
DB_DIR = DATA_DIR / "db"
CONFIG_DIR = DATA_DIR / "config"
ARTIFACT_DIR = DATA_DIR / "artifacts"

PATH_SPACES_CONFIG = CONFIG_DIR / "config_spaces.json"
PATH_DB = DB_DIR / "confluence_mirror.db"
PATH_MODEL = CONFIG_DIR / "type_model.joblib"

for directory in (DB_DIR, CONFIG_DIR):
    directory.mkdir(parents=True, exist_ok=True)
