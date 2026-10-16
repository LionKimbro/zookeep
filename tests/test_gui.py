"""A fresh real-Tk process exercises the queue bridge and visible field behavior."""

import subprocess
import sys
import unittest


class GuiTests(unittest.TestCase):
    def test_project_type_switch_save_and_shutdown_in_real_tk(self):
        script = r'''
from pathlib import Path
import tempfile
import tkinter
import traceback
from zookeep import project, runtime, tk

errors = []
steps = {"phase": "load", "attempts": 0}
real_realize = tk.realize_project_specification_window

def check():
    try:
        steps["attempts"] += 1
        assert steps["attempts"] < 100, "GUI did not reach expected state"
        if not tk.g["hydrated"]:
            tk.g["root"].after(50, check)
            return
        state = tk.g["snapshot"]["state"]
        phase = steps["phase"]
        if phase == "load":
            assert state["python"]
            assert isinstance(tk.windows["spec"]["toplevel"], tkinter.Toplevel)
            assert str(tk.fields["repo-type"]["widget"].cget("state")) == "normal"
            assert list(tk.fields["repo-type"]["widget"]["values"]) == ["basic-2026", "python-2026-03"]
            tk.fields["name"]["var"].set("Notes")
            tk.fields["repository.name"]["var"].set("notes")
            tk.fields["repo-type"]["var"].set("basic-2026")
            steps["phase"] = "basic"
        elif phase == "basic" and not state["python"]:
            assert not tk.fields["python.distribution.name"]["widget"].winfo_ismapped()
            assert str(tk.widgets["description"].cget("foreground")) == tk.COLORS["blue"]
            tk.fields["repo-type"]["var"].set("custom-2027")
            steps["phase"] = "custom"
        elif phase == "custom" and not state["supported"]:
            assert str(tk.widgets["description"].cget("foreground")) == tk.COLORS["red"]
            assert str(tk.widgets["setup"].cget("state")) == "disabled"
            tk.handle_when_user_requests_save()
            steps["phase"] = "saved"
        elif phase == "saved" and state["status-kind"] == "success":
            zoo = project.read_zoo_project(root)
            assert zoo["repo-type"] == "custom-2027"
            assert "python" not in zoo
            assert "license" not in zoo
            assert not (root / ".git").exists()
            tk.handle_when_debug_mode_is_requested()
            tk.handle_when_debug_snapshot_is_copied()
            assert "worker-alive" in tk.g["root"].clipboard_get()
            steps["phase"] = "closed"
            tk.handle_when_user_requests_close()
            return
        tk.g["root"].after(50, check)
    except Exception as exc:
        errors.append(traceback.format_exc())
        tk.handle_when_user_requests_close()

def realize_and_schedule(root):
    real_realize(root)
    tk.g["root"].after(100, check)

tk.realize_project_specification_window = realize_and_schedule
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    tk.run_editor(root)
assert not errors, errors
assert steps["phase"] == "closed", steps
assert not runtime.g["thread"].is_alive()
'''
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
