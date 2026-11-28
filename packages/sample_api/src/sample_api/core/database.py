"""商品別の見本データを読み取り専用のSQLiteで参照する。"""

import sqlite3
from functools import cached_property

from fastapi import HTTPException


class SampleDatabase:
    def __init__(self, schema: str, rows: list[tuple]):
        self.schema = schema
        self.rows = rows

    @cached_property
    def connection(self):
        db = sqlite3.connect(":memory:", check_same_thread=False)
        db.row_factory = sqlite3.Row
        db.execute(self.schema)
        placeholders = ", ".join("?" for _ in self.rows[0])
        db.executemany(f"INSERT INTO records VALUES ({placeholders})", self.rows)
        db.commit()
        db.execute("PRAGMA query_only = ON")
        return db

    def all(self, query, *params):
        return [dict(row) for row in self.connection.execute(query, params)]

    def one(self, query, *params):
        row = self.connection.execute(query, params).fetchone()
        if row is None:
            raise HTTPException(404, "該当するデータがありません")
        return dict(row)
