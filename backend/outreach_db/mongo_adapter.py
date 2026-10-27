"""Supabase PostgREST-compatible MongoDB query adapter."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from outreach_db.client import ensure_indexes, get_database, strip_mongo_id


@dataclass
class ApiResult:
    data: Any = None
    count: int | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_or_filter(raw: str) -> dict[str, Any]:
    """Parse PostgREST or filter: login.ilike.%x%,name.ilike.%x%."""
    clauses: list[dict[str, Any]] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        match = re.match(r"^([^.]+)\.(ilike|eq|neq|gt|gte|lt|lte|is)\.(.+)$", part, re.I)
        if not match:
            continue
        fld, op, val = match.group(1), match.group(2).lower(), match.group(3)
        if op == "ilike":
            pattern = val.strip("%")
            if pattern:
                clauses.append({fld: {"$regex": re.escape(pattern), "$options": "i"}})
        elif op == "eq":
            clauses.append({fld: val})
        elif op == "is" and val.lower() == "null":
            clauses.append({fld: None})
    return {"$or": clauses} if clauses else {}


def _is_null(value: Any) -> bool:
    return value is None or value == ""


def _sanitize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Text-indexed collections reject non-string `language` (including null)."""
    out = dict(doc)
    if not isinstance(out.get("language"), str):
        out.pop("language", None)
    return out


class NotProxy:
    def __init__(self, builder: MongoTableQuery) -> None:
        self._builder = builder

    def is_(self, column: str, value: str) -> MongoTableQuery:
        if value == "null":
            self._builder._filters.append({column: {"$nin": [None, ""]}})
        return self._builder


class MongoTableQuery:
    def __init__(self, table: str) -> None:
        self._table = table
        self._filters: list[dict[str, Any]] = []
        self._select_cols: str | None = "*"
        self._count_exact = False
        self._head_only = False
        self._order: tuple[str, bool] | None = None
        self._limit: int | None = None
        self._skip: int | None = None
        self._single = False
        self._op: str | None = None
        self._payload: Any = None
        self._on_conflict: str | None = None
        self.not_ = NotProxy(self)

    def select(self, columns: str = "*", *, count: str | None = None, head: bool = False) -> MongoTableQuery:
        self._select_cols = columns
        if count == "exact":
            self._count_exact = True
        if head:
            self._head_only = True
        return self

    def insert(self, payload: dict[str, Any] | list[dict[str, Any]]) -> MongoTableQuery:
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload: dict[str, Any]) -> MongoTableQuery:
        self._op = "update"
        self._payload = payload
        return self

    def upsert(self, payload: dict[str, Any] | list[dict[str, Any]], *, on_conflict: str | None = None) -> MongoTableQuery:
        self._op = "upsert"
        self._payload = payload
        self._on_conflict = on_conflict
        return self

    def delete(self) -> MongoTableQuery:
        self._op = "delete"
        return self

    def eq(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: value})
        return self

    def neq(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: {"$ne": value}})
        return self

    def gte(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: {"$gte": value}})
        return self

    def lte(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: {"$lte": value}})
        return self

    def gt(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: {"$gt": value}})
        return self

    def lt(self, column: str, value: Any) -> MongoTableQuery:
        self._filters.append({column: {"$lt": value}})
        return self

    def ilike(self, column: str, pattern: str) -> MongoTableQuery:
        escaped = re.escape(str(pattern).strip("%"))
        self._filters.append({column: {"$regex": f"^{escaped}$", "$options": "i"}})
        return self

    def in_(self, column: str, values: list[Any]) -> MongoTableQuery:
        self._filters.append({column: {"$in": list(values)}})
        return self

    def or_(self, filters: str) -> MongoTableQuery:
        parsed = _parse_or_filter(filters)
        if parsed:
            self._filters.append(parsed)
        return self

    def is_(self, column: str, value: str) -> MongoTableQuery:
        if value == "null":
            self._filters.append(
                {
                    "$or": [
                        {column: None},
                        {column: {"$exists": False}},
                        {column: ""},
                    ]
                }
            )
        return self

    def order(self, column: str, *, desc: bool = False) -> MongoTableQuery:
        self._order = (column, desc)
        return self

    def limit(self, count: int) -> MongoTableQuery:
        self._limit = count
        return self

    def range(self, start: int, end: int) -> MongoTableQuery:
        self._skip = max(0, start)
        self._limit = max(0, end - start + 1)
        return self

    def single(self) -> MongoTableQuery:
        self._single = True
        self._limit = 1
        return self

    def _query(self) -> dict[str, Any]:
        if not self._filters:
            return {}
        if len(self._filters) == 1:
            return self._filters[0]
        return {"$and": self._filters}

    def _col(self):
        ensure_indexes()
        return get_database()[self._table]

    def _project(self, doc: dict[str, Any]) -> dict[str, Any]:
        row = strip_mongo_id(_sanitize_doc(doc)) or {}
        cols = (self._select_cols or "*").strip()
        if cols == "*":
            return row
        keys = {c.strip() for c in cols.split(",") if c.strip()}
        return {k: row.get(k) for k in keys if k in row}

    def _ensure_id(self, doc: dict[str, Any]) -> dict[str, Any]:
        out = dict(doc)
        if not out.get("id"):
            out["id"] = str(uuid.uuid4())
        now = _now_iso()
        out.setdefault("created_at", now)
        out.setdefault("updated_at", now)
        return out

    def execute(self) -> ApiResult:
        col = self._col()
        query = self._query()

        if self._op == "insert":
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            inserted: list[dict[str, Any]] = []
            for row in rows:
                doc = self._ensure_id(_sanitize_doc(dict(row)))
                col.insert_one(doc)
                inserted.append(self._project(doc))
            data = inserted[0] if self._single and inserted else inserted
            return ApiResult(data=data)

        if self._op == "update":
            patch = dict(self._payload or {})
            patch["updated_at"] = _now_iso()
            col.update_many(query, {"$set": patch})
            if self._select_cols is not None:
                cursor = col.find(query)
                rows = [self._project(doc) for doc in cursor]
                if self._single:
                    return ApiResult(data=rows[0] if rows else None)
                return ApiResult(data=rows)
            return ApiResult(data=[])

        if self._op == "upsert":
            rows = self._payload if isinstance(self._payload, list) else [self._payload]
            conflict = self._on_conflict or "id"
            upserted: list[dict[str, Any]] = []
            for row in rows:
                doc = _sanitize_doc(dict(row))
                key_val = doc.get(conflict)
                if key_val is None:
                    doc = self._ensure_id(doc)
                    key_val = doc[conflict]
                filter_doc = {conflict: key_val}
                existing = col.find_one(filter_doc)
                if existing:
                    doc.setdefault("id", existing.get("id"))
                    doc.setdefault("created_at", existing.get("created_at"))
                else:
                    doc = self._ensure_id(doc)
                doc["updated_at"] = _now_iso()
                col.update_one(filter_doc, {"$set": doc}, upsert=True)
                upserted.append(self._project(doc))
            data = upserted[0] if self._single and upserted else upserted
            return ApiResult(data=data)

        if self._op == "delete":
            col.delete_many(query)
            return ApiResult(data=[])

        total = col.count_documents(query) if self._count_exact else None
        if self._head_only:
            return ApiResult(data=[], count=total or col.count_documents(query))

        cursor = col.find(query)
        if self._order:
            field, desc = self._order
            cursor = cursor.sort(field, -1 if desc else 1)
        if self._skip:
            cursor = cursor.skip(self._skip)
        if self._limit is not None:
            cursor = cursor.limit(self._limit)

        rows = [self._project(doc) for doc in cursor]
        if self._single:
            return ApiResult(data=rows[0] if rows else None, count=total)
        return ApiResult(data=rows, count=total)


class MongoRpcQuery:
    def __init__(self, name: str) -> None:
        self._name = name

    def execute(self) -> ApiResult:
        if self._name == "rebuild_github_user_country_stats":
            from outreach_db.rpc import rebuild_github_user_country_stats

            rebuild_github_user_country_stats()
            return ApiResult(data=[])
        raise RuntimeError(f"Unknown RPC: {self._name}")


class MongoSupabaseClient:
    """Drop-in subset of supabase.Client for table/rpc operations."""

    def table(self, name: str) -> MongoTableQuery:
        return MongoTableQuery(name)

    def rpc(self, name: str, params: dict[str, Any] | None = None) -> MongoRpcQuery:
        return MongoRpcQuery(name)


class MongoOnlyClient:
    """MongoDB-only client — no Supabase connection."""

    def __init__(self, mongo_client: MongoSupabaseClient) -> None:
        self._mongo = mongo_client

    def table(self, name: str) -> MongoTableQuery:
        return self._mongo.table(name)

    def rpc(self, name: str, params: dict[str, Any] | None = None) -> MongoRpcQuery:
        return self._mongo.rpc(name, params)


class HybridSupabaseClient:
    """Routes table/rpc to MongoDB; auth/storage stay on Supabase."""

    def __init__(self, real_client: Any, mongo_client: MongoSupabaseClient) -> None:
        self._real = real_client
        self._mongo = mongo_client

    def table(self, name: str) -> MongoTableQuery:
        return self._mongo.table(name)

    def rpc(self, name: str, params: dict[str, Any] | None = None) -> MongoRpcQuery:
        return self._mongo.rpc(name, params)

    @property
    def auth(self):
        return self._real.auth

    @property
    def storage(self):
        return self._real.storage

    @property
    def postgrest(self):
        return self._real.postgrest
