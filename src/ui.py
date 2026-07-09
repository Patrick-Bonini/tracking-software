from __future__ import annotations

import sqlite3
from datetime import datetime
from tkinter import StringVar, ttk

import customtkinter as ctk

from .db import (
    complete_time_entry,
    activate_project,
    create_manual_time_entry,
    create_project,
    create_task,
    create_time_entry,
    archive_project,
    delete_time_entry,
    fetch_projects,
    fetch_active_projects,
    fetch_settings,
    fetch_recent_time_entries,
    fetch_tasks_for_project,
    fetch_time_entry,
    update_settings,
    update_time_entry,
)
from .invoice import generate_invoice_pdf


DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class TimeEntryDialog(ctk.CTkToplevel):
    def __init__(self, master: ctk.CTk, title: str, entry_id: int | None = None) -> None:
        super().__init__(master)
        self.title(title)
        self.geometry("560x520")
        self.resizable(False, False)
        self.transient(master)
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.result: dict[str, object] | None = None
        self.entry_id = entry_id
        self.projects = [
            {"id": row["id"], "name": row["name"], "hourly_rate": row["hourly_rate"]}
            for row in fetch_active_projects()
        ]
        self.project_var = StringVar(value=self.projects[0]["name"] if self.projects else "No active projects")
        self.task_var = StringVar(value="Select a task")
        self.start_var = StringVar()
        self.end_var = StringVar()
        self.duration_var = StringVar()
        self.invoiced_var = ctk.BooleanVar(value=False)
        self.task_options: list[dict[str, object]] = []

        self._build_ui()
        self._load_default_values()
        self._sync_tasks(self.project_var.get())

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        container = ctk.CTkFrame(self)
        container.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")
        container.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(container, text=self.title(), font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 12), sticky="w"
        )

        ctk.CTkLabel(container, text="Project").grid(row=1, column=0, padx=18, pady=8, sticky="w")
        self.project_combo = ctk.CTkComboBox(container, values=[project["name"] for project in self.projects] or ["No active projects"], variable=self.project_var, command=self._sync_tasks, state="readonly")
        self.project_combo.grid(row=1, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(container, text="Task").grid(row=2, column=0, padx=18, pady=8, sticky="w")
        self.task_combo = ctk.CTkComboBox(container, values=["Select a task"], variable=self.task_var, state="readonly")
        self.task_combo.grid(row=2, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(container, text=f"Start time ({DATETIME_FORMAT})").grid(row=3, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(container, textvariable=self.start_var).grid(row=3, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(container, text=f"End time ({DATETIME_FORMAT})").grid(row=4, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(container, textvariable=self.end_var).grid(row=4, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(container, text="Duration seconds").grid(row=5, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(container, textvariable=self.duration_var).grid(row=5, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkCheckBox(container, text="Already invoiced", variable=self.invoiced_var).grid(
            row=6, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="w"
        )

        button_row = ctk.CTkFrame(container, fg_color="transparent")
        button_row.grid(row=7, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="ew")
        button_row.grid_columnconfigure((0, 1), weight=1)

        ctk.CTkButton(button_row, text="Cancel", command=self._cancel).grid(row=0, column=0, padx=(0, 8), sticky="ew")
        ctk.CTkButton(button_row, text="Save", command=self._save).grid(row=0, column=1, padx=(8, 0), sticky="ew")

    def _load_default_values(self) -> None:
        if self.entry_id is None:
            now = datetime.now().replace(microsecond=0).strftime(DATETIME_FORMAT)
            self.start_var.set(now)
            self.end_var.set("")
            self.duration_var.set("")
            return

        row = fetch_time_entry(self.entry_id)
        if row is None:
            return

        project_name = next((project["name"] for project in self.projects if project["id"] == row["project_id"]), self.project_var.get())
        self.project_var.set(project_name)
        self.start_var.set(row["start_time"])
        self.end_var.set(row["end_time"] or "")
        self.duration_var.set(str(row["duration_seconds"]))
        self.invoiced_var.set(bool(row["is_invoiced"]))
        self._sync_tasks(project_name)
        task_name = next((task["name"] for task in self.task_options if task["id"] == row["task_id"]), "Select a task")
        self.task_var.set(task_name)

    def _sync_tasks(self, selected_name: str) -> None:
        project = next((item for item in self.projects if item["name"] == selected_name), None)
        if project is None:
            self.task_options = []
            self.task_combo.configure(values=["Select a task"])
            self.task_combo.set("Select a task")
            return

        task_rows = fetch_tasks_for_project(int(project["id"]))
        self.task_options = [{"id": row["id"], "name": row["task_name"]} for row in task_rows]
        task_values = [task["name"] for task in self.task_options] or ["Select a task"]
        self.task_combo.configure(values=task_values)
        self.task_combo.set(task_values[0])

    def _cancel(self) -> None:
        self.result = None
        self.destroy()

    def _save(self) -> None:
        try:
            project = next(project for project in self.projects if project["name"] == self.project_var.get())
        except StopIteration:
            return

        task_id = next((task["id"] for task in self.task_options if task["name"] == self.task_var.get()), None)
        start_time = datetime.strptime(self.start_var.get().strip(), DATETIME_FORMAT)
        end_text = self.end_var.get().strip()
        end_time: datetime | None = None
        if end_text:
            end_time = datetime.strptime(end_text, DATETIME_FORMAT)

        duration_text = self.duration_var.get().strip()
        if end_time is not None:
            duration_seconds = max(int((end_time - start_time).total_seconds()), 0)
        elif duration_text:
            duration_seconds = max(int(duration_text), 0)
        else:
            duration_seconds = 0

        self.result = {
            "project_id": int(project["id"]),
            "task_id": task_id,
            "start_time": start_time.strftime(DATETIME_FORMAT),
            "end_time": end_time.strftime(DATETIME_FORMAT) if end_time is not None else None,
            "duration_seconds": duration_seconds,
            "is_invoiced": bool(self.invoiced_var.get()),
        }
        self.destroy()


class TimerController:
    def __init__(self, display: ctk.CTkLabel) -> None:
        self.display = display
        self.running = False
        self.paused = False
        self.start_timestamp: datetime | None = None
        self.paused_timestamp: datetime | None = None
        self.entry_id: int | None = None
        self.project_id: int | None = None
        self.task_id: int | None = None
        self.accumulated_seconds = 0
        self._tick_job: str | None = None

    def start(self, project_id: int, task_id: int | None) -> None:
        if self.running:
            return

        if self.paused and self.entry_id is not None:
            self.running = True
            self.paused = False
            self.start_timestamp = datetime.now()
            self._schedule_tick()
            return

        self.project_id = project_id
        self.task_id = task_id
        self.start_timestamp = datetime.now()
        self.paused_timestamp = None
        self.accumulated_seconds = 0
        self.entry_id = create_time_entry(project_id, task_id, self.start_timestamp.strftime(DATETIME_FORMAT))
        self.running = True
        self.paused = False
        self._schedule_tick()

    def stop(self) -> None:
        if not self.running or self.start_timestamp is None or self.entry_id is None:
            return

        now = datetime.now()
        self.accumulated_seconds += max(int((now - self.start_timestamp).total_seconds()), 0)
        self.running = False
        self.paused = True
        self.paused_timestamp = now
        self.start_timestamp = None
        self._cancel_tick()
        self.display.configure(text=self._format_duration(self.accumulated_seconds))

    def save(self) -> bool:
        if self.entry_id is None or self.project_id is None or self.task_id is None:
            return False

        if self.running and self.start_timestamp is not None:
            now = datetime.now()
            total_seconds = self.accumulated_seconds + max(int((now - self.start_timestamp).total_seconds()), 0)
            end_timestamp = now
        elif self.paused and self.paused_timestamp is not None:
            total_seconds = self.accumulated_seconds
            end_timestamp = self.paused_timestamp
        else:
            return False

        complete_time_entry(self.entry_id, end_timestamp.strftime(DATETIME_FORMAT), total_seconds)
        self._clear_state()
        self.display.configure(text="00:00:00")
        return True

    def reset(self) -> None:
        if self.entry_id is not None:
            delete_time_entry(self.entry_id)
        self._clear_state()
        self._cancel_tick()
        self.display.configure(text="00:00:00")

    def _clear_state(self) -> None:
        self.running = False
        self.paused = False
        self.start_timestamp = None
        self.paused_timestamp = None
        self.entry_id = None
        self.project_id = None
        self.task_id = None
        self.accumulated_seconds = 0

    def _schedule_tick(self) -> None:
        self._cancel_tick()
        self._tick_job = self.display.after(1000, self._tick)

    def _tick(self) -> None:
        if not self.running or self.start_timestamp is None:
            return

        elapsed_seconds = self.accumulated_seconds + max(int((datetime.now() - self.start_timestamp).total_seconds()), 0)
        self.display.configure(text=self._format_duration(elapsed_seconds))
        self._schedule_tick()

    @staticmethod
    def _format_duration(duration_seconds: int) -> str:
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _cancel_tick(self) -> None:
        if self._tick_job is not None:
            self.display.after_cancel(self._tick_job)
            self._tick_job = None


class ApplicationUI(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk) -> None:
        super().__init__(master, corner_radius=0)
        self.master = master
        self.project_options: list[dict[str, object]] = []
        self.all_projects: list[dict[str, object]] = []
        self.task_options: list[dict[str, object]] = []
        self.project_var = StringVar(value="No active projects")
        self.task_var = StringVar(value="Select a task")
        self.project_name_var = StringVar()
        self.project_rate_var = StringVar()
        self.task_project_var = StringVar(value="No active projects")
        self.task_name_var = StringVar()
        self.invoice_project_var = StringVar(value="No active projects")
        self.bill_from_name_var = StringVar()
        self.bill_from_phone_var = StringVar()
        self.bill_from_address_var = StringVar()
        self.bank_name_var = StringVar()
        self.account_name_var = StringVar()
        self.account_number_var = StringVar()
        self.logo_path_var = StringVar()
        self.invoice_client_name_var = StringVar()
        self.invoice_client_phone_var = StringVar()
        self.invoice_client_address_var = StringVar()
        self.invoice_start_date_var = StringVar()
        self.invoice_end_date_var = StringVar()
        self.invoice_status_var = StringVar(value="")
        self.timer_display: ctk.CTkLabel | None = None
        self.project_combo: ctk.CTkComboBox | None = None
        self.task_combo: ctk.CTkComboBox | None = None
        self.invoice_project_combo: ctk.CTkComboBox | None = None
        self.task_project_combo: ctk.CTkComboBox | None = None
        self.invoice_generate_button: ctk.CTkButton | None = None
        self.timer_controller: TimerController | None = None
        self.start_button: ctk.CTkButton | None = None
        self.stop_button: ctk.CTkButton | None = None
        self.save_button: ctk.CTkButton | None = None
        self.reset_button: ctk.CTkButton | None = None
        self.timesheet_tree: ttk.Treeview | None = None
        self.projects_tree: ttk.Treeview | None = None
        self.tasks_tree: ttk.Treeview | None = None
        self.timer_status_var = StringVar(value="Ready")
        self.pack(fill="both", expand=True)
        self._configure_layout()
        self._build_header()
        self._build_tabs()

    def _configure_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, corner_radius=0)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header,
            text="Tracking Software",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        title.grid(row=0, column=0, padx=24, pady=(18, 2), sticky="w")

        subtitle = ctk.CTkLabel(
            header,
            text="Local time tracking, manual entry, and invoice preparation",
            text_color=("gray35", "gray70"),
        )
        subtitle.grid(row=1, column=0, padx=24, pady=(0, 18), sticky="w")

    def _build_tabs(self) -> None:
        tabs = ctk.CTkTabview(self)
        tabs.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="nsew")
        tabs.add("Timer")
        tabs.add("Timesheet / Manual Entry")
        tabs.add("Projects / Invoicing")

        timer_tab = self._make_scrollable_tab(tabs.tab("Timer"))
        timesheet_tab = self._make_scrollable_tab(tabs.tab("Timesheet / Manual Entry"))
        projects_tab = self._make_scrollable_tab(tabs.tab("Projects / Invoicing"))

        self._build_timer_tab(timer_tab)
        self._build_timesheet_tab(timesheet_tab)
        self._build_projects_tab(projects_tab)

    def _make_scrollable_tab(self, tab: ctk.CTkFrame) -> ctk.CTkScrollableFrame:
        tab.grid_rowconfigure(0, weight=1)
        tab.grid_columnconfigure(0, weight=1)
        scrollable = ctk.CTkScrollableFrame(tab, fg_color="transparent")
        scrollable.grid(row=0, column=0, sticky="nsew")
        scrollable.grid_columnconfigure(0, weight=1)
        return scrollable

    def _build_timer_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)

        self.project_options = [
            {"id": row["id"], "name": row["name"], "hourly_rate": row["hourly_rate"]}
            for row in fetch_active_projects()
        ]
        self.task_options = []

        timer_card = ctk.CTkFrame(tab)
        timer_card.grid(row=0, column=0, padx=(0, 12), pady=12, sticky="nsew")
        timer_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(timer_card, text="Timer", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, padx=20, pady=(20, 8), sticky="w"
        )

        project_options = [project["name"] for project in self.project_options] or ["No active projects"]
        self.project_var.set(project_options[0])
        self.project_combo = ctk.CTkComboBox(
            timer_card,
            values=project_options,
            state="readonly",
            variable=self.project_var,
            command=self._on_project_selected,
        )
        self.project_combo.grid(row=1, column=0, padx=20, pady=8, sticky="ew")

        self.task_combo = ctk.CTkComboBox(
            timer_card,
            values=["Select a task"],
            state="readonly",
            variable=self.task_var,
        )
        self.task_combo.set("Select a task")
        self.task_combo.grid(row=2, column=0, padx=20, pady=8, sticky="ew")

        self.timer_display = ctk.CTkLabel(
            timer_card,
            text="00:00:00",
            font=ctk.CTkFont(size=42, weight="bold"),
        )
        self.timer_display.grid(row=3, column=0, padx=20, pady=(28, 12), sticky="ew")

        self.timer_controller = TimerController(self.timer_display)

        button_row = ctk.CTkFrame(timer_card, fg_color="transparent")
        button_row.grid(row=4, column=0, padx=20, pady=(0, 20), sticky="ew")
        button_row.grid_columnconfigure((0, 1, 2), weight=1)

        self.start_button = ctk.CTkButton(button_row, text="Start", command=self._start_timer)
        self.start_button.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.stop_button = ctk.CTkButton(button_row, text="Stop", command=self._stop_timer)
        self.stop_button.grid(row=0, column=1, padx=8, sticky="ew")
        self.save_button = ctk.CTkButton(button_row, text="Save", command=self._save_timer)
        self.save_button.grid(row=0, column=2, padx=8, sticky="ew")
        self.reset_button = ctk.CTkButton(button_row, text="Reset", command=self._reset_timer)
        self.reset_button.grid(row=0, column=3, padx=(8, 0), sticky="ew")

        summary_card = ctk.CTkFrame(tab)
        summary_card.grid(row=0, column=1, padx=(12, 0), pady=12, sticky="nsew")
        summary_card.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            summary_card,
            text="Live session details",
            font=ctk.CTkFont(size=18, weight="bold"),
        ).grid(row=0, column=0, padx=20, pady=(20, 8), sticky="w")

        ctk.CTkLabel(
            summary_card,
            text="Timer logic will attach here in the next slice.\nThis panel is reserved for active task metadata and status.",
            justify="left",
        ).grid(row=1, column=0, padx=20, pady=(0, 20), sticky="nw")

        ctk.CTkLabel(summary_card, textvariable=self.timer_status_var, text_color=("gray35", "gray70")).grid(
            row=2, column=0, padx=20, pady=(0, 20), sticky="w"
        )

        self._on_project_selected(self.project_var.get())

    def _current_project(self) -> dict[str, object] | None:
        current_name = self.project_var.get()
        for project in self.project_options:
            if project["name"] == current_name:
                return project
        return None

    def _on_project_selected(self, selected_name: str) -> None:
        project = next((item for item in self.project_options if item["name"] == selected_name), None)
        if project is None:
            self.task_options = []
            if self.task_combo is not None:
                self.task_combo.configure(values=["Select a task"])
                self.task_combo.set("Select a task")
            return

        task_rows = fetch_tasks_for_project(int(project["id"]))
        self.task_options = [{"id": row["id"], "name": row["task_name"]} for row in task_rows]
        task_values = [task["name"] for task in self.task_options] or ["No tasks available"]

        if self.task_combo is not None:
            self.task_combo.configure(values=task_values)
            self.task_combo.set(task_values[0])

    def _current_task_id(self) -> int | None:
        current_name = self.task_var.get()
        for task in self.task_options:
            if task["name"] == current_name:
                return int(task["id"])
        return None

    def _start_timer(self) -> None:
        if self.timer_controller is None:
            return

        project = self._current_project()
        if project is None:
            return

        task_id = self._current_task_id()
        self.timer_controller.start(int(project["id"]), task_id)
        if self.timer_controller.running:
            self.timer_status_var.set("Running")
        elif self.timer_controller.paused:
            self.timer_status_var.set("Paused - ready to save")

    def _stop_timer(self) -> None:
        if self.timer_controller is not None:
            self.timer_controller.stop()
            self.timer_status_var.set("Paused - ready to save")
        self.refresh_timesheet_entries()

    def _save_timer(self) -> None:
        if self.timer_controller is None:
            return

        if self.timer_controller.save():
            self.timer_status_var.set("Saved")
            self.refresh_timesheet_entries()

    def _reset_timer(self) -> None:
        if self.timer_controller is not None:
            self.timer_controller.reset()
            self.timer_status_var.set("Ready")
        self.refresh_timesheet_entries()

    def _build_timesheet_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        controls = ctk.CTkFrame(tab)
        controls.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        controls.grid_columnconfigure((0, 1, 2), weight=1)

        ctk.CTkButton(controls, text="Add Entry", command=self._add_manual_entry).grid(row=0, column=0, padx=12, pady=12, sticky="ew")
        ctk.CTkButton(controls, text="Edit Selected", command=self._edit_selected_entry).grid(row=0, column=1, padx=12, pady=12, sticky="ew")
        ctk.CTkButton(controls, text="Delete Selected", command=self._delete_selected_entry).grid(row=0, column=2, padx=12, pady=12, sticky="ew")

        table_card = ctk.CTkFrame(tab)
        table_card.grid(row=1, column=0, padx=12, pady=(8, 12), sticky="nsew")
        table_card.grid_rowconfigure(0, weight=1)
        table_card.grid_columnconfigure(0, weight=1)

        columns = ("date", "project", "task", "start", "end", "duration", "invoice")
        self.timesheet_tree = ttk.Treeview(table_card, columns=columns, show="headings", height=12)
        headings = {
            "date": "Date",
            "project": "Project",
            "task": "Task",
            "start": "Start",
            "end": "End",
            "duration": "Duration",
            "invoice": "Invoiced",
        }
        for column, heading in headings.items():
            self.timesheet_tree.heading(column, text=heading)
            self.timesheet_tree.column(column, width=120, anchor="center")
        self.timesheet_tree.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")
        self.refresh_timesheet_entries()

    def refresh_timesheet_entries(self) -> None:
        if self.timesheet_tree is None:
            return

        for item in self.timesheet_tree.get_children():
            self.timesheet_tree.delete(item)

        for row in fetch_recent_time_entries():
            start_time = row["start_time"] or ""
            end_time = row["end_time"] or ""
            duration = self._format_duration(int(row["duration_seconds"]))
            invoiced = "Yes" if row["is_invoiced"] else "No"
            self.timesheet_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    start_time.split(" ")[0],
                    row["project_name"],
                    row["task_name"] or "",
                    start_time,
                    end_time,
                    duration,
                    invoiced,
                ),
            )

    def _selected_entry_id(self) -> int | None:
        if self.timesheet_tree is None:
            return None
        selection = self.timesheet_tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _open_entry_dialog(self, title: str, entry_id: int | None = None) -> None:
        dialog = TimeEntryDialog(self.master, title, entry_id=entry_id)
        self.wait_window(dialog)
        if dialog.result is None:
            return

        payload = dialog.result
        if entry_id is None:
            create_manual_time_entry(
                int(payload["project_id"]),
                payload["task_id"],
                str(payload["start_time"]),
                payload["end_time"],
                int(payload["duration_seconds"]),
                bool(payload["is_invoiced"]),
            )
        else:
            update_time_entry(
                entry_id,
                int(payload["project_id"]),
                payload["task_id"],
                str(payload["start_time"]),
                payload["end_time"],
                int(payload["duration_seconds"]),
                bool(payload["is_invoiced"]),
            )

        self.refresh_timesheet_entries()

    def _add_manual_entry(self) -> None:
        self._open_entry_dialog("Add Time Entry")

    def _edit_selected_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            return
        self._open_entry_dialog("Edit Time Entry", entry_id=entry_id)

    def _delete_selected_entry(self) -> None:
        entry_id = self._selected_entry_id()
        if entry_id is None:
            return
        delete_time_entry(entry_id)
        self.refresh_timesheet_entries()

    @staticmethod
    def _format_duration(duration_seconds: int) -> str:
        hours, remainder = divmod(duration_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def _build_projects_tab(self, tab: ctk.CTkFrame) -> None:
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_columnconfigure(1, weight=1)
        tab.grid_rowconfigure(0, weight=1)

        left_column = ctk.CTkFrame(tab)
        left_column.grid(row=0, column=0, padx=(12, 8), pady=12, sticky="nsew")
        left_column.grid_columnconfigure(0, weight=1)

        project_card = ctk.CTkFrame(left_column)
        project_card.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        project_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(project_card, text="Projects", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 10), sticky="w"
        )

        ctk.CTkLabel(project_card, text="Name").grid(row=1, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(project_card, textvariable=self.project_name_var).grid(row=1, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(project_card, text="Hourly rate").grid(row=2, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(project_card, textvariable=self.project_rate_var).grid(row=2, column=1, padx=18, pady=8, sticky="ew")

        action_row = ctk.CTkFrame(project_card, fg_color="transparent")
        action_row.grid(row=3, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="ew")
        action_row.grid_columnconfigure((0, 1, 2), weight=1)
        ctk.CTkButton(action_row, text="Create Project", command=self._create_project).grid(row=0, column=0, padx=(0, 6), sticky="ew")
        ctk.CTkButton(action_row, text="Archive Selected", command=self._archive_selected_project).grid(row=0, column=1, padx=6, sticky="ew")
        ctk.CTkButton(action_row, text="Activate Selected", command=self._activate_selected_project).grid(row=0, column=2, padx=(6, 0), sticky="ew")

        projects_list_card = ctk.CTkFrame(left_column)
        projects_list_card.grid(row=1, column=0, padx=12, pady=8, sticky="nsew")
        projects_list_card.grid_rowconfigure(0, weight=1)
        projects_list_card.grid_columnconfigure(0, weight=1)

        self.projects_tree = ttk.Treeview(projects_list_card, columns=("name", "rate", "status"), show="headings", height=10)
        for column, heading, width in (("name", "Project", 200), ("rate", "Rate", 100), ("status", "Status", 100)):
            self.projects_tree.heading(column, text=heading)
            self.projects_tree.column(column, width=width, anchor="center")
        self.projects_tree.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        task_card = ctk.CTkFrame(left_column)
        task_card.grid(row=2, column=0, padx=12, pady=(8, 12), sticky="ew")
        task_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(task_card, text="Tasks", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 10), sticky="w"
        )
        ctk.CTkLabel(task_card, text="Project").grid(row=1, column=0, padx=18, pady=8, sticky="w")
        self.task_project_combo = ctk.CTkComboBox(task_card, values=["No active projects"], variable=self.task_project_var, state="readonly", command=self._refresh_task_list_for_manager)
        self.task_project_combo.grid(row=1, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(task_card, text="Task name").grid(row=2, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(task_card, textvariable=self.task_name_var).grid(row=2, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkButton(task_card, text="Add Task", command=self._create_task).grid(row=3, column=0, columnspan=2, padx=18, pady=(8, 18), sticky="ew")

        tasks_list_card = ctk.CTkFrame(left_column)
        tasks_list_card.grid(row=3, column=0, padx=12, pady=(0, 12), sticky="nsew")
        tasks_list_card.grid_rowconfigure(0, weight=1)
        tasks_list_card.grid_columnconfigure(0, weight=1)

        self.tasks_tree = ttk.Treeview(tasks_list_card, columns=("task",), show="headings", height=8)
        self.tasks_tree.heading("task", text="Task")
        self.tasks_tree.column("task", width=320, anchor="w")
        self.tasks_tree.grid(row=0, column=0, padx=16, pady=16, sticky="nsew")

        right_column = ctk.CTkFrame(tab)
        right_column.grid(row=0, column=1, padx=(8, 12), pady=12, sticky="nsew")
        right_column.grid_columnconfigure(0, weight=1)

        settings_card = ctk.CTkFrame(right_column)
        settings_card.grid(row=0, column=0, padx=12, pady=(12, 8), sticky="ew")
        settings_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(settings_card, text="Invoice Settings", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 10), sticky="w"
        )
        fields = [
            ("Bill From Name", self.bill_from_name_var),
            ("Bill From Phone", self.bill_from_phone_var),
            ("Bill From Address", self.bill_from_address_var),
            ("Bank Name", self.bank_name_var),
            ("Account Name", self.account_name_var),
            ("Account Number", self.account_number_var),
            ("Logo Path", self.logo_path_var),
        ]
        for index, (label, variable) in enumerate(fields, start=1):
            ctk.CTkLabel(settings_card, text=label).grid(row=index, column=0, padx=18, pady=6, sticky="w")
            ctk.CTkEntry(settings_card, textvariable=variable).grid(row=index, column=1, padx=18, pady=6, sticky="ew")

        ctk.CTkButton(settings_card, text="Save Settings", command=self._save_settings).grid(
            row=len(fields) + 1, column=0, columnspan=2, padx=18, pady=(10, 18), sticky="ew"
        )

        invoice_card = ctk.CTkFrame(right_column)
        invoice_card.grid(row=1, column=0, padx=12, pady=8, sticky="nsew")
        invoice_card.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(invoice_card, text="Invoice Generator", font=ctk.CTkFont(size=18, weight="bold")).grid(
            row=0, column=0, columnspan=2, padx=18, pady=(18, 10), sticky="w"
        )
        ctk.CTkLabel(invoice_card, text="Project").grid(row=1, column=0, padx=18, pady=8, sticky="w")
        self.invoice_project_combo = ctk.CTkComboBox(invoice_card, values=["No active projects"], variable=self.invoice_project_var, state="readonly")
        self.invoice_project_combo.grid(row=1, column=1, padx=18, pady=8, sticky="ew")
        ctk.CTkLabel(invoice_card, text="Start date").grid(row=2, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(invoice_card, textvariable=self.invoice_start_date_var, placeholder_text="YYYY-MM-DD").grid(row=2, column=1, padx=18, pady=8, sticky="ew")
        ctk.CTkLabel(invoice_card, text="End date").grid(row=3, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(invoice_card, textvariable=self.invoice_end_date_var, placeholder_text="YYYY-MM-DD").grid(row=3, column=1, padx=18, pady=8, sticky="ew")

        ctk.CTkLabel(invoice_card, text="Client Name").grid(row=4, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(invoice_card, textvariable=self.invoice_client_name_var).grid(row=4, column=1, padx=18, pady=8, sticky="ew")
        ctk.CTkLabel(invoice_card, text="Client Phone").grid(row=5, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(invoice_card, textvariable=self.invoice_client_phone_var).grid(row=5, column=1, padx=18, pady=8, sticky="ew")
        ctk.CTkLabel(invoice_card, text="Client Address").grid(row=6, column=0, padx=18, pady=8, sticky="w")
        ctk.CTkEntry(invoice_card, textvariable=self.invoice_client_address_var).grid(row=6, column=1, padx=18, pady=8, sticky="ew")

        self.invoice_generate_button = ctk.CTkButton(invoice_card, text="Generate Invoice", command=self._generate_invoice)
        self.invoice_generate_button.grid(row=7, column=0, columnspan=2, padx=18, pady=(10, 8), sticky="ew")

        ctk.CTkLabel(invoice_card, textvariable=self.invoice_status_var, text_color=("gray35", "gray70")).grid(
            row=8, column=0, columnspan=2, padx=18, pady=(0, 18), sticky="w"
        )

        today = datetime.now().date()
        first_day = today.replace(day=1)
        self.invoice_start_date_var.set(first_day.isoformat())
        self.invoice_end_date_var.set(today.isoformat())

        self._reload_project_sources()
        self._reload_project_table()
        self._load_settings_into_form()
        self._refresh_task_list_for_manager(self.task_project_var.get())

    def _reload_project_sources(self) -> None:
        current_timer_name = self.project_var.get()
        current_manager_name = self.task_project_var.get()
        current_invoice_name = self.invoice_project_var.get()

        self.project_options = [
            {"id": row["id"], "name": row["name"], "hourly_rate": row["hourly_rate"]}
            for row in fetch_active_projects()
        ]
        self.all_projects = [
            {"id": row["id"], "name": row["name"], "hourly_rate": row["hourly_rate"], "status": row["status"]}
            for row in fetch_projects()
        ]

        active_names = [project["name"] for project in self.project_options] or ["No active projects"]
        selected_timer_name = current_timer_name if current_timer_name in active_names else active_names[0]
        selected_manager_name = current_manager_name if current_manager_name in active_names else active_names[0]
        selected_invoice_name = current_invoice_name if current_invoice_name in active_names else active_names[0]

        self.project_var.set(selected_timer_name)
        self.task_project_var.set(selected_manager_name)
        self.invoice_project_var.set(selected_invoice_name)

        if self.project_combo is not None:
            self.project_combo.configure(values=active_names)
            self.project_combo.set(selected_timer_name)
        if self.task_project_combo is not None:
            self.task_project_combo.configure(values=active_names)
            self.task_project_combo.set(selected_manager_name)
        if self.invoice_project_combo is not None:
            self.invoice_project_combo.configure(values=active_names)
            self.invoice_project_combo.set(selected_invoice_name)

        self._on_project_selected(self.project_var.get())

    def _reload_project_table(self) -> None:
        if self.projects_tree is None:
            return

        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)

        for row in self.all_projects:
            self.projects_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(row["name"], f"{float(row['hourly_rate']):.2f}", row["status"].title()),
            )

    def _refresh_task_list_for_manager(self, selected_name: str) -> None:
        project = next((item for item in self.project_options if item["name"] == selected_name), None)
        if project is None:
            if self.tasks_tree is not None:
                for item in self.tasks_tree.get_children():
                    self.tasks_tree.delete(item)
            return

        if self.tasks_tree is None:
            return

        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)

        for row in fetch_tasks_for_project(int(project["id"])):
            self.tasks_tree.insert("", "end", iid=str(row["id"]), values=(row["task_name"],))

    def _selected_project_id(self) -> int | None:
        if self.projects_tree is None:
            return None
        selection = self.projects_tree.selection()
        if not selection:
            return None
        return int(selection[0])

    def _create_project(self) -> None:
        name = self.project_name_var.get().strip()
        rate_text = self.project_rate_var.get().strip()
        if not name:
            return

        try:
            hourly_rate = float(rate_text or 0)
            create_project(name, hourly_rate)
        except ValueError:
            return
        except sqlite3.IntegrityError:
            return

        self.project_name_var.set("")
        self.project_rate_var.set("")
        self._reload_project_sources()
        self._reload_project_table()

    def _archive_selected_project(self) -> None:
        project_id = self._selected_project_id()
        if project_id is None:
            return
        archive_project(project_id)
        self._reload_project_sources()
        self._reload_project_table()

    def _activate_selected_project(self) -> None:
        project_id = self._selected_project_id()
        if project_id is None:
            return
        activate_project(project_id)
        self._reload_project_sources()
        self._reload_project_table()

    def _create_task(self) -> None:
        project = next((item for item in self.project_options if item["name"] == self.task_project_var.get()), None)
        task_name = self.task_name_var.get().strip()
        if project is None or not task_name:
            return

        try:
            create_task(int(project["id"]), task_name)
        except sqlite3.IntegrityError:
            return

        self.task_name_var.set("")
        self._refresh_task_list_for_manager(project["name"])
        self._on_project_selected(self.project_var.get())

    def _load_settings_into_form(self) -> None:
        row = fetch_settings()
        self.bill_from_name_var.set(row["bill_from_name"])
        self.bill_from_phone_var.set(row["bill_from_phone"])
        self.bill_from_address_var.set(row["bill_from_address"])
        self.bank_name_var.set(row["bank_name"])
        self.account_name_var.set(row["account_name"])
        self.account_number_var.set(row["account_number"])
        self.logo_path_var.set(row["logo_path"])

    def _save_settings(self) -> None:
        update_settings(
            self.bill_from_name_var.get(),
            self.bill_from_phone_var.get(),
            self.bill_from_address_var.get(),
            self.bank_name_var.get(),
            self.account_name_var.get(),
            self.account_number_var.get(),
            self.logo_path_var.get(),
        )

    def _generate_invoice(self) -> None:
        project = next((item for item in self.project_options if item["name"] == self.invoice_project_var.get()), None)
        if project is None:
            self.invoice_status_var.set("Select an active project first.")
            return

        client_name = self.invoice_client_name_var.get().strip()
        client_phone = self.invoice_client_phone_var.get().strip()
        client_address = self.invoice_client_address_var.get().strip()
        start_date = self.invoice_start_date_var.get().strip()
        end_date = self.invoice_end_date_var.get().strip()

        if not client_name or not client_address or not start_date or not end_date:
            self.invoice_status_var.set("Client details and date range are required.")
            return

        try:
            invoice_path = generate_invoice_pdf(
                int(project["id"]),
                start_date,
                end_date,
                client_name,
                client_phone,
                client_address,
            )
        except ValueError as exc:
            self.invoice_status_var.set(str(exc))
            return
        except Exception as exc:
            self.invoice_status_var.set(f"Invoice generation failed: {exc}")
            return

        self.refresh_timesheet_entries()
        self.invoice_status_var.set(f"Invoice created: {invoice_path}")