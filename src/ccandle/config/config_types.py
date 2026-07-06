from ccandle.config.config_db import PATH_MODEL
import joblib

artifact = joblib.load(PATH_MODEL)
TYPE_LIST = set(artifact["classes"])
ADMINISTRATIVE_TYPES = ["meeting_minutes", "release_notes", "performance_test"]
TYPE_ADMIN_FILTER = (f"page_type NOT IN ({', '.join(repr(t) for t in ADMINISTRATIVE_TYPES)})")