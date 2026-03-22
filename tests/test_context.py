from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from memory.context import append_note, load_notes


class MemoryContextTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.notes_dir = Path("tests/.tmp_notes")
        if self.notes_dir.exists():
            shutil.rmtree(self.notes_dir)
        self.notes_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        if self.notes_dir.exists():
            shutil.rmtree(self.notes_dir)

    async def test_append_note_writes_journal_entry(self) -> None:
        journal_path = await append_note("hello companion", self.notes_dir)
        content = journal_path.read_text(encoding="utf-8")
        self.assertIn("hello companion", content)

    async def test_load_notes_reads_markdown_files(self) -> None:
        sample = self.notes_dir / "profile.md"
        sample.write_text("favorite model: ollama", encoding="utf-8")

        notes = await load_notes(self.notes_dir)

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["name"], "profile.md")
        self.assertIn("favorite model", notes[0]["content"])


if __name__ == "__main__":
    unittest.main()
