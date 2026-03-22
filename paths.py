from __future__ import annotations

import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent


if getattr(sys, "frozen", False):
    RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    RUNTIME_DIR = Path(sys.executable).resolve().parent
else:
    RESOURCE_DIR = PROJECT_DIR
    RUNTIME_DIR = PROJECT_DIR


CONFIG_PATH = RUNTIME_DIR / "config.yaml"
ASSETS_DIR = RESOURCE_DIR / "assets"
MEMORY_DIR = RUNTIME_DIR / "memory"
NOTES_DIR = MEMORY_DIR / "notes"
DB_PATH = MEMORY_DIR / "companion.db"
