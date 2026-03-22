from __future__ import annotations

import asyncio
from datetime import datetime
from pathlib import Path

from paths import NOTES_DIR




async def append_note(note: str, notes_dir: Path | None = None) -> Path:
    target_dir = notes_dir or NOTES_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    journal_path = target_dir / "journal.md"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"- [{timestamp}] {note.strip()}\n"
    await asyncio.to_thread(_append_text, journal_path, entry)
    return journal_path


async def load_notes(notes_dir: Path | None = None) -> list[dict[str, str]]:
    target_dir = notes_dir or NOTES_DIR
    if not target_dir.exists():
        return []

    notes: list[dict[str, str]] = []
    for path in sorted(target_dir.glob("*.md")):
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        if content.strip():
            notes.append({"name": path.name, "content": content})
    return notes


def _append_text(path: Path, content: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(content)


