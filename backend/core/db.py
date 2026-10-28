"""
Database access, always inside the ProofPath schema.

The Supabase project is shared with Nirikshan, whose tables are in `public`. Every query here goes
through `db.table(...)`, which is bound to settings.SUPABASE_SCHEMA, so ProofPath code cannot read or
write Nirikshan's tables by accident. The schema must be listed under Data API -> Exposed schemas.
"""
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from core.config import settings


class Database:
    def __init__(self):
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        self.schema = settings.SUPABASE_SCHEMA

    def table(self, table_name: str):
        return self.client.schema(self.schema).table(table_name)

    def rpc(self, fn: str, params: Optional[Dict[str, Any]] = None):
        return self.client.schema(self.schema).rpc(fn, params or {})

    @property
    def storage(self):
        return self.client.storage.from_(settings.STORAGE_BUCKET)

    def fetch_all(self, table_name: str, **filters) -> List[Dict[str, Any]]:
        query = self.table(table_name).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        return query.execute().data or []

    def fetch_one(self, table_name: str, **filters) -> Optional[Dict[str, Any]]:
        query = self.table(table_name).select("*")
        for k, v in filters.items():
            query = query.eq(k, v)
        res = query.limit(1).execute()
        return res.data[0] if res.data else None

    def insert(self, table_name: str, record: Dict[str, Any]) -> Dict[str, Any]:
        res = self.table(table_name).insert(record).execute()
        return res.data[0] if res.data else {}

    def update(self, table_name: str, record_id: str, updates: Dict[str, Any], id_field: str = "id") -> Dict[str, Any]:
        res = self.table(table_name).update(updates).eq(id_field, record_id).execute()
        return res.data[0] if res.data else {}


db = Database()
