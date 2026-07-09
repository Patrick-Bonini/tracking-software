from __future__ import annotations

import os
import sys
from pathlib import Path


def _configure_tk_paths() -> None:
    base_python = Path(sys.base_prefix)
    tcl_library = base_python / "tcl" / "tcl8.6"
    tk_library = base_python / "tcl" / "tk8.6"

    if tcl_library.exists():
        os.environ.setdefault("TCL_LIBRARY", str(tcl_library))
    if tk_library.exists():
        os.environ.setdefault("TK_LIBRARY", str(tk_library))


_configure_tk_paths()

import customtkinter as ctk

from .db import initialize_database
from .ui import ApplicationUI


class TrackingApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Tracking Software")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.after(0, self._center_window)

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.ui = ApplicationUI(self)

    def _center_window(self) -> None:
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_position = max((screen_width // 2) - (width // 2), 0)
        y_position = max((screen_height // 2) - (height // 2), 0)
        self.geometry(f"{width}x{height}+{x_position}+{y_position}")


def main() -> None:
    initialize_database()
    app = TrackingApp()
    app.mainloop()