from __future__ import annotations

import importlib
import shutil
import sys
import types
import unittest
from pathlib import Path


class FakeCursor:
    def __init__(self, connection, query: str) -> None:
        self.connection = connection
        self.query = query

    async def fetchone(self):
        if "SELECT value FROM config" in self.query:
            key = self.connection.last_select_key
            value = self.connection.config_table.get(key)
            if value is None:
                return None
            return {"value": value}
        if "SELECT COUNT(*) FROM alerts_sent" in self.query:
            return (len(self.connection.alerts_table),)
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.row_factory = None
        self.config_table: dict[str, str] = {}
        self.alerts_table: list[tuple[str, str]] = []
        self.events_table: list[tuple[str, str, str]] = []
        self.last_select_key = ""

    async def executescript(self, _script: str) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def execute(self, query: str, params=()):
        if "INSERT INTO config" in query:
            self.config_table[params[0]] = params[1]
        elif "INSERT INTO alerts_sent" in query:
            self.alerts_table.append((params[0], params[1]))
        elif "INSERT INTO events" in query:
            self.events_table.append((params[0], params[1], params[2]))
        elif "SELECT value FROM config" in query:
            self.last_select_key = params[0]
        return FakeCursor(self, query)


aiosqlite = types.ModuleType("aiosqlite")
aiosqlite.Row = dict

async def connect(_path: Path):
    return FakeConnection()

aiosqlite.connect = connect
sys.modules["aiosqlite"] = aiosqlite

import memory.db as memory_db_module
memory_db_module = importlib.reload(memory_db_module)
MemoryStore = memory_db_module.MemoryStore


class MemoryStoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp_dir = Path("tests/.tmp_memory")
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)
        self.tmp_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.tmp_dir.exists():
            shutil.rmtree(self.tmp_dir)

    async def test_config_round_trip_and_alert_recording(self) -> None:
        store = MemoryStore(self.tmp_dir / "companion.db")
        await store.initialize()
        await store.set_config_value("selected_model", "groq")
        await store.record_alert("CPU high", "telegram")

        selected = await store.get_config_value("selected_model")

        self.assertEqual(selected, "groq")
        assert store.connection is not None
        cursor = await store.connection.execute("SELECT COUNT(*) FROM alerts_sent")
        row = await cursor.fetchone()
        self.assertEqual(row[0], 1)
        await store.close()


if __name__ == "__main__":
    unittest.main()
