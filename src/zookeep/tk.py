"""Main-thread Tk shell: callbacks enqueue; projection consumes worker snapshots."""

from functools import partial
import json
from queue import Empty
import tkinter as tk
from tkinter import ttk

from zookeep import project, runtime


COLORS = {
    "black": "#000000", "panel": "#03101e", "field": "#071d35",
    "blue": "#00bfff", "text": "#91d8ff", "dim": "#427cac",
    "edge": "#15598c", "red": "#ff617a", "success": "#59baff",
}
# Main-thread only. State is a detached projection, never the core's live dict.
g = {"root": None, "snapshot": None, "hydrated": False, "closing": False, "debug": False}
widgets = {}
fields = {}
windows = {}  # The editor is a singleton with stable id "spec".


def configure_electric_blue_theme():
    style = ttk.Style(g["root"])
    style.theme_use("clam")
    style.configure(".", background=COLORS["black"], foreground=COLORS["text"], font=("Segoe UI", 10))
    style.configure("TEntry", fieldbackground=COLORS["field"], foreground=COLORS["text"],
                    insertcolor=COLORS["blue"], bordercolor=COLORS["edge"], padding=6)
    style.configure("TCombobox", fieldbackground=COLORS["field"], background=COLORS["panel"],
                    foreground=COLORS["text"], arrowcolor=COLORS["blue"], bordercolor=COLORS["edge"], padding=6)
    style.map("TCombobox", fieldbackground=[("readonly", COLORS["field"])],
              foreground=[("readonly", COLORS["text"]), ("disabled", COLORS["dim"])])
    style.configure("TButton", background=COLORS["field"], foreground=COLORS["blue"],
                    bordercolor=COLORS["edge"], padding=(14, 8))
    style.map("TButton", background=[("active", "#0b3960")], foreground=[("disabled", COLORS["dim"])])
    style.configure("Title.TLabel", foreground=COLORS["blue"], font=("Segoe UI", 20, "bold"))
    style.configure("Hint.TLabel", foreground=COLORS["blue"])
    g["root"].option_add("*TCombobox*Listbox.background", COLORS["field"])
    g["root"].option_add("*TCombobox*Listbox.foreground", COLORS["text"])
    g["root"].option_add("*TCombobox*Listbox.selectBackground", "#15598c")


def run_editor(root):
    g.update(root=None, snapshot=None, hydrated=False, closing=False, debug=False)
    widgets.clear()
    fields.clear()
    windows.clear()
    anchor = tk.Tk()
    anchor.withdraw()
    g["root"] = anchor
    try:
        configure_electric_blue_theme()
        realize_project_specification_window(root)
        runtime.start_runtime(root)
        anchor.after(50, handle_routine_worker_snapshot_update)
        anchor.mainloop()
    finally:
        if runtime.g["thread"] is not None and runtime.g["thread"].is_alive():
            runtime.post_event({"type": "CLOSE_REQUESTED"})
            runtime.g["thread"].join()
        try:
            anchor.destroy()
        except tk.TclError:
            pass
        windows.clear()
        widgets.clear()
        fields.clear()
        g["root"] = None


def realize_project_specification_window(root):
    window = tk.Toplevel(g["root"])
    window.title(f"Zookeep · {root.name}")
    window.configure(background=COLORS["black"])
    window.resizable(False, False)
    windows["spec"] = {"toplevel": window, "kind": "spec", "multiplicity": "singleton", "state": None}
    frame = ttk.Frame(window, padding=24)
    frame.grid(sticky="nsew")
    ttk.Label(frame, text="ZOOKEEP", style="Title.TLabel").grid(row=0, columnspan=2, sticky="w")
    ttk.Label(frame, text=str(root), foreground=COLORS["dim"]).grid(row=1, columnspan=2, sticky="w", pady=(0, 18))
    for row, spec in enumerate(project.SPEC_FIELD_SPECS, start=2):
        name = spec["name"]
        label = ttk.Label(frame, text=spec["label"])
        label.grid(row=row, column=0, sticky="w", padx=(0, 20), pady=6)
        var = tk.StringVar(value=spec["default"])
        if "choice" in spec["kind"]:
            state = "normal" if spec["kind"] == "editable-choice" else "readonly"
            widget = ttk.Combobox(frame, textvariable=var, values=spec["choices"], state=state, width=36)
        else:
            widget = ttk.Entry(frame, textvariable=var, width=38)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        fields[name] = {"var": var, "widget": widget, "label": label, "spec": spec}
        var.trace_add("write", partial(handle_when_specification_field_changes, name))
    row = len(project.SPEC_FIELD_SPECS) + 2
    widgets["description"] = ttk.Label(frame, wraplength=570, style="Hint.TLabel")
    widgets["description"].grid(row=row, columnspan=2, sticky="w", pady=(16, 10))
    buttons = ttk.Frame(frame)
    buttons.grid(row=row + 1, columnspan=2, sticky="e", pady=(8, 12))
    for column, (name, label, callback) in enumerate([
        ("save", "Save", handle_when_user_requests_save),
        ("setup", "Save & setup", handle_when_user_requests_setup),
        ("close", "Close", handle_when_user_requests_close),
    ]):
        widgets[name] = ttk.Button(buttons, text=label, command=callback)
        widgets[name].grid(row=0, column=column, padx=(8, 0))
    widgets["status"] = ttk.Label(frame, text="Loading project…", wraplength=570)
    widgets["status"].grid(row=row + 2, columnspan=2, sticky="w", pady=(8, 0))
    window.protocol("WM_DELETE_WINDOW", handle_when_user_requests_close)
    window.bind("<Control-Shift-Alt-D>", handle_when_debug_mode_is_requested)
    window.bind("<Control-Shift-Alt-d>", handle_when_debug_mode_is_requested)
    fields["name"]["widget"].focus_set()


def handle_when_specification_field_changes(name, *_trace_args):
    if g["hydrated"] and not g["closing"]:
        runtime.post_event({"type": "FIELD_CHANGED", "name": name, "value": fields[name]["var"].get()})


def collect_form_fields():
    return {name: record["var"].get() for name, record in fields.items()}


def handle_when_user_requests_save():
    runtime.post_event({"type": "SAVE_REQUESTED", "fields": collect_form_fields()})


def handle_when_user_requests_setup():
    runtime.post_event({"type": "SAVE_AND_SETUP_REQUESTED", "fields": collect_form_fields()})


def handle_when_user_requests_close():
    if not g["closing"]:
        g["closing"] = True
        widgets["status"].configure(text="Closing after pending work completes…")
        runtime.post_event({"type": "CLOSE_REQUESTED"})


def handle_routine_worker_snapshot_update():
    while True:
        try:
            g["snapshot"] = runtime.queues["outbox"].get_nowait()
        except Empty:
            break
    if g["snapshot"] is not None:
        project_specification_window()
        if g["snapshot"]["state"]["phase"] == "closed" and not runtime.g["thread"].is_alive():
            g["root"].quit()
            return
    g["root"].after(50, handle_routine_worker_snapshot_update)


def project_specification_window():
    state = g["snapshot"]["state"]
    windows["spec"]["state"] = state
    if not g["hydrated"] and state["fields"]:
        for name, record in fields.items():
            record["var"].set(state["fields"].get(name, ""))
        g["hydrated"] = True
    busy = state["phase"] != "editing" or g["closing"]
    for name, record in fields.items():
        visible = state["python"] or not (name.startswith("python.") or name == "license")
        for key in ("label", "widget"):
            if visible:
                record[key].grid()
            else:
                record[key].grid_remove()
        mode = "readonly" if record["spec"]["kind"] == "choice" else "normal"
        record["widget"].configure(state="disabled" if busy else mode)
    widgets["save"].configure(state="disabled" if busy else "normal")
    widgets["setup"].configure(state="disabled" if busy or not state["supported"] else "normal")
    widgets["description"].configure(text=state["description"],
        foreground=COLORS["blue"] if state["supported"] else COLORS["red"])
    if not g["closing"]:
        widgets["status"].configure(text=state["status"],
            foreground=COLORS["red"] if state["status-kind"] == "error" else COLORS["text"])


def handle_when_debug_mode_is_requested(_event=None):
    if g["debug"]:
        return
    g["debug"] = True
    menu = tk.Menu(windows["spec"]["toplevel"], background=COLORS["panel"], foreground=COLORS["blue"])
    debug = tk.Menu(menu, tearoff=False, background=COLORS["panel"], foreground=COLORS["blue"])
    debug.add_command(label="Copy runtime snapshot", command=handle_when_debug_snapshot_is_copied)
    menu.add_cascade(label="Debug", menu=debug)
    windows["spec"]["toplevel"].configure(menu=menu)


def handle_when_debug_snapshot_is_copied():
    snapshot = dict(g["snapshot"] or {})
    snapshot["worker-alive"] = runtime.g["thread"].is_alive()
    snapshot["queues"] = {name: queue.qsize() for name, queue in runtime.queues.items()}
    snapshot["windows"] = {name: record["kind"] for name, record in windows.items()}
    g["root"].clipboard_clear()
    g["root"].clipboard_append(json.dumps(snapshot, indent=2))
