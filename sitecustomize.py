from __future__ import annotations

import os
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
TCL_LIBRARY = BASE_DIR / ".venv" / "tcl" / "tcl8.6"
TK_LIBRARY = BASE_DIR / ".venv" / "tcl" / "tk8.6"
SYSTEM_PYTHON = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python314"

if not TCL_LIBRARY.exists():
    TCL_LIBRARY = SYSTEM_PYTHON / "tcl" / "tcl8.6"

if not TK_LIBRARY.exists():
    TK_LIBRARY = SYSTEM_PYTHON / "tcl" / "tk8.6"

if TCL_LIBRARY.exists():
    os.environ.setdefault("TCL_LIBRARY", str(TCL_LIBRARY))

if TK_LIBRARY.exists():
    os.environ.setdefault("TK_LIBRARY", str(TK_LIBRARY))