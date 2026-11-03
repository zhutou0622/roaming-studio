"""Frozen/​source resource paths.

PyInstaller (onefile) unpacks bundled data into ``sys._MEIPASS``; when running
from source the project root is the parent of this package.
"""
from __future__ import annotations

import os
import sys


def base_dir() -> str:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS  # type: ignore[attr-defined]
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_path(*parts: str) -> str:
    return os.path.join(base_dir(), *parts)
