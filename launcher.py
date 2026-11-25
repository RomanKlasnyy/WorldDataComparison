"""Frozen-application entry point (PyInstaller)."""

from __future__ import annotations

import multiprocessing

from worlddata.ui.app import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
