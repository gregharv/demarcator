from __future__ import annotations

from demarcator.services import DemarcatorService
from demarcator.store import SQLiteRepository

DEFAULT_DB_PATH = "demarcator.db"


def create_seeded_service(db_path: str = DEFAULT_DB_PATH) -> DemarcatorService:
    store = SQLiteRepository(db_path)
    store.initialize_schema()
    if store.is_empty():
        store.seed_demo_data()
    return DemarcatorService(store)
