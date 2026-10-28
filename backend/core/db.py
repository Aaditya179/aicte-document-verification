"""
Database access, always inside the ProofPath schema.

The Supabase project is shared with Nirikshan, whose tables are in `public`. Every query here goes
through `db.table(...)`, which is bound to settings.SUPABASE_SCHEMA, so ProofPath code cannot read or
write Nirikshan's tables by accident. The schema must be listed under Data API -> Exposed schemas.
"""
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional

import httpx
from postgrest import SyncPostgrestClient
from supabase import Client, create_client

from core.config import settings


class Database:
    def __init__(self):
        self.client: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)
        self.schema = settings.SUPABASE_SCHEMA
        # client.schema() builds a new PostgREST client, and with it a new HTTP connection, on every call.
        # One client with its own pool means a query costs a round trip, not a TLS handshake. HTTP/1.1,
        # because `parallel` sends queries from several threads and one shared HTTP/2 connection drops them.
        base = self.client.schema(self.schema)
        self.rest = SyncPostgrestClient(str(base.base_url), schema=self.schema, headers=dict(base.headers),
                                        http_client=httpx.Client(timeout=30, follow_redirects=True,
                                                                 limits=httpx.Limits(max_connections=16)))
        base.session.close()

    def table(self, table_name: str):
        return self.rest.table(table_name)

    def rpc(self, fn: str, params: Optional[Dict[str, Any]] = None):
        return self.rest.rpc(fn, params or {})

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


def parallel(*calls: Callable[[], Any]) -> list:
    """Run independent queries at once. Each is a round trip to Supabase, so this cuts waiting, not work.
    Each call gets its own threads, so a call made inside another one never waits on a shared, busy pool."""
    with ThreadPoolExecutor(max_workers=len(calls) or 1, thread_name_prefix="db") as pool:
        return [f.result() for f in [pool.submit(c) for c in calls]]


db = Database()
