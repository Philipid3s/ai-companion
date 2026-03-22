from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from paths import DB_PATH




class MemoryStore:
    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or DB_PATH
        self.connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        if self.connection is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = await aiosqlite.connect(self.db_path)
            self.connection.row_factory = aiosqlite.Row

    async def initialize(self) -> None:
        await self.connect()
        assert self.connection is not None
        await self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                type TEXT NOT NULL,
                content TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'info'
            );

            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS alerts_sent (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                message TEXT NOT NULL,
                channel TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pending_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                channel TEXT NOT NULL,
                message TEXT NOT NULL,
                UNIQUE(channel, message)
            );
            """
        )
        await self.connection.commit()

    async def close(self) -> None:
        if self.connection is not None:
            await self.connection.close()
            self.connection = None

    async def log_event(self, event_type: str, content: str, severity: str = "info") -> None:
        await self.connect()
        assert self.connection is not None
        await self.connection.execute(
            "INSERT INTO events (type, content, severity) VALUES (?, ?, ?)",
            (event_type, content, severity),
        )
        await self.connection.commit()

    async def record_alert(self, message: str, channel: str) -> None:
        await self.connect()
        assert self.connection is not None
        await self.connection.execute(
            "INSERT INTO alerts_sent (message, channel) VALUES (?, ?)",
            (message, channel),
        )
        await self.connection.commit()

    async def enqueue_message(self, channel: str, message: str) -> None:
        await self.connect()
        assert self.connection is not None
        await self.connection.execute(
            "INSERT OR IGNORE INTO pending_messages (channel, message) VALUES (?, ?)",
            (channel, message),
        )
        await self.connection.commit()

    async def list_pending_messages(self, channel: str) -> list[str]:
        await self.connect()
        assert self.connection is not None
        cursor = await self.connection.execute(
            "SELECT message FROM pending_messages WHERE channel = ? ORDER BY id ASC",
            (channel,),
        )
        rows = await cursor.fetchall()
        return [str(row["message"]) for row in rows]

    async def remove_pending_message(self, channel: str, message: str) -> None:
        await self.connect()
        assert self.connection is not None
        await self.connection.execute(
            "DELETE FROM pending_messages WHERE channel = ? AND message = ?",
            (channel, message),
        )
        await self.connection.commit()

    async def set_config_value(self, key: str, value: Any) -> None:
        await self.connect()
        assert self.connection is not None
        encoded = json.dumps(value)
        await self.connection.execute(
            """
            INSERT INTO config (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, encoded),
        )
        await self.connection.commit()

    async def get_config_value(self, key: str, default: Any = None) -> Any:
        await self.connect()
        assert self.connection is not None
        cursor = await self.connection.execute(
            "SELECT value FROM config WHERE key = ?",
            (key,),
        )
        row = await cursor.fetchone()
        if row is None:
            return default
        return json.loads(row["value"])


