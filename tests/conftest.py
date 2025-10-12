"""Загальні фікстури для pytest."""
from __future__ import annotations

import sys
from pathlib import Path

# Додаємо src до sys.path, щоб імпортувати cortexwatcher без інсталяції пакета
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if SRC.exists():
    sys.path.insert(0, str(SRC))
