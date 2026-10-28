"""
An in-memory stand-in for the PostgREST query builder, covering the calls the API makes:
select / insert / update / delete / upsert with eq, neq, in_, order, limit and range.
Routes run unchanged against it, so access rules are tested through the real endpoints.
"""
import itertools
import uuid
from types import SimpleNamespace

# Like Postgres `default now()`: increasing, so ordering by created_at follows insertion order
_clock = itertools.count(1)


def _now() -> str:
    return f"2026-10-28T10:00:00.{next(_clock):06d}+00:00"


class FakeQuery:
    def __init__(self, store: dict, table: str):
        self.store, self.table = store, table
        self.rows = store.setdefault(table, [])
        self.op, self.payload, self.filters = "select", None, []
        self.order_by, self.limit_n, self.offset = [], None, 0
        self.conflict = None

    # operations
    def select(self, *_cols, count=None):
        self.op = "select"
        return self

    def insert(self, rows):
        self.op, self.payload = "insert", rows
        return self

    def update(self, values):
        self.op, self.payload = "update", values
        return self

    def delete(self):
        self.op = "delete"
        return self

    def upsert(self, row, on_conflict=None):
        self.op, self.payload, self.conflict = "upsert", row, on_conflict
        return self

    # filters and modifiers
    def eq(self, col, value):
        self.filters.append(lambda r: r.get(col) == value)
        return self

    def neq(self, col, value):
        self.filters.append(lambda r: r.get(col) != value)
        return self

    def is_(self, col, value):
        expected = None if value == "null" else value
        self.filters.append(lambda r: r.get(col) is expected)
        return self

    def in_(self, col, values):
        values = list(values)
        self.filters.append(lambda r: r.get(col) in values)
        return self

    def order(self, col, desc=False):
        self.order_by.append((col, desc))
        return self

    def limit(self, n):
        self.limit_n = n
        return self

    def range(self, start, end):
        self.offset, self.limit_n = start, end - start + 1
        return self

    def _matching(self):
        return [r for r in self.rows if all(f(r) for f in self.filters)]

    def execute(self):
        if self.op == "insert":
            many = isinstance(self.payload, list)
            new = [{"id": str(uuid.uuid4()), "created_at": _now(), **row} for row in (self.payload if many else [self.payload])]
            if self.table == "rooms":                  # area_sqm is a generated column in Postgres
                for r in new:
                    r["area_sqm"] = r["length_m"] * r["width_m"]
            self.rows.extend(new)
            return SimpleNamespace(data=[dict(r) for r in new], count=None)
        if self.op == "upsert":
            keys = (self.conflict or "id").split(",")
            existing = next((r for r in self.rows if all(r.get(k) == self.payload.get(k) for k in keys)), None)
            if existing:
                existing.update(self.payload)
                return SimpleNamespace(data=[dict(existing)], count=None)
            self.op = "insert"
            return self.execute()
        matched = self._matching()
        if self.op == "update":
            for r in matched:
                r.update(self.payload)
            return SimpleNamespace(data=[dict(r) for r in matched], count=None)
        if self.op == "delete":
            self.store[self.table] = [r for r in self.rows if r not in matched]
            return SimpleNamespace(data=[dict(r) for r in matched], count=None)
        for col, desc in reversed(self.order_by):
            matched.sort(key=lambda r: (r.get(col) is None, r.get(col)), reverse=desc)
        sliced = matched[self.offset:]
        if self.limit_n is not None:
            sliced = sliced[:self.limit_n]
        return SimpleNamespace(data=[dict(r) for r in sliced], count=len(matched))


class FakeStorage:
    def __init__(self):
        self.files: dict[str, bytes] = {}

    def create_signed_upload_url(self, path):
        return {"signed_url": f"https://storage.test/upload/{path}?token=t", "token": "t", "path": path}

    def create_signed_url(self, path, expires_in):
        return {"signedURL": f"https://storage.test/sign/{path}?expires={expires_in}"}

    def download(self, path):
        if path not in self.files:
            raise RuntimeError("Object not found")
        return self.files[path]


class FakeDB:
    def __init__(self):
        self.store: dict[str, list] = {}
        self.storage = FakeStorage()
        self.audit: list[dict] = []

    def table(self, name):
        return FakeQuery(self.store, name)

    def rpc(self, fn, params=None):
        if fn == "audit_append":
            self.audit.append(params)
            return SimpleNamespace(execute=lambda: SimpleNamespace(data=len(self.audit)))
        return SimpleNamespace(execute=lambda: SimpleNamespace(data={"ok": True, "events_checked": len(self.audit), "broken_at_id": None}))

    def rows(self, name):
        return self.store.get(name, [])
