"""Neon's SQL-over-HTTPS transport for the Flask Worker's single-statement queries."""

import json
from urllib.parse import urlsplit

from pg8000.converters import PG_TYPES, PY_TYPES, make_params
from pg8000.dbapi import convert_paramstyle


class NeonConnection:
    def __init__(self, url):
        host = urlsplit(url).hostname or ""
        if not host.endswith(".neon.tech"):
            raise ValueError("DATABASE_URL must point to a Neon database.")
        self.url = url
        self.endpoint = f"https://{host}/sql"

    def cursor(self):
        return NeonCursor(self)

    def commit(self):
        pass  # Each app write is one atomic statement, committed by Neon.

    def rollback(self):
        raise RuntimeError("HTTPS queries are autocommitted; use direct PostgreSQL for migrations.")

    def close(self):
        pass


class NeonCursor:
    def __init__(self, connection):
        self.connection = connection
        self.rows = iter(())
        self.rowcount = -1

    def execute(self, query, params=()):
        from pyodide.ffi import run_sync
        from workers import fetch

        sql, values = convert_paramstyle("format", query, params)
        response = run_sync(fetch(
            self.connection.endpoint, method="POST", redirect="manual",
            headers={"Content-Type": "application/json",
                     "Neon-Connection-String": self.connection.url,
                     "Neon-Raw-Text-Output": "true", "Neon-Array-Mode": "true"},
            body=json.dumps({"query": sql, "params": make_params(PY_TYPES, values)}),
        ))
        if not response.ok:
            # Never include response bodies or credentials in user-facing errors.
            raise RuntimeError(f"Neon SQL request failed (HTTP {response.status}). Check Worker logs and database configuration.")
        result = run_sync(response.json())
        fields = result.get("fields", [])
        self.rows = iter([
            {field["name"]: (None if value is None else PG_TYPES.get(field["dataTypeID"], str)(value))
             for field, value in zip(fields, row)}
            for row in result.get("rows", [])
        ])
        self.rowcount = result.get("rowCount", -1)

    def fetchone(self):
        return next(self.rows, None)

    def fetchall(self):
        return list(self.rows)

    def close(self):
        self.rows = iter(())
