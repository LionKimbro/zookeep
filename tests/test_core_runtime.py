from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from zookeep import core, project, runtime


class CoreRuntimeTests(unittest.TestCase):
    def setUp(self):
        core.initialize_core_state()

    def test_basic_save_needs_no_python_or_license_and_custom_type_can_save(self):
        for repo_type in ["basic-2026", "future-type"]:
            core.reduce_event({"type": "PROJECT_LOADED", "zoo": {"repo-type": repo_type}})
            fields = dict(core.g["fields"], name="Notes")
            fields["repository.name"] = "notes"
            fields["license"] = ""
            effects = core.reduce_event({"type": "SAVE_REQUESTED", "fields": fields})
            self.assertEqual(effects[0]["type"], "WRITE_SPEC")
            zoo = project.make_spec_zoo_project(fields)
            self.assertNotIn("python", zoo)
            self.assertNotIn("license", zoo)
            if repo_type == "future-type":
                self.assertIn("Unsupported presently", core.g["description"])
                core.reduce_event({"type": "SPEC_SAVED"})
                self.assertEqual(core.reduce_event({"type": "SAVE_AND_SETUP_REQUESTED", "fields": fields}), [])
                self.assertEqual(core.g["status-kind"], "error")

    def test_snapshots_are_independent_and_save_uses_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime.start_runtime(root)
            try:
                loaded = runtime.queues["outbox"].get(timeout=3)
                fields = dict(loaded["state"]["fields"], name="Notes")
                fields.update({"repo-type": "basic-2026", "repository.name": "notes"})
                worker_ids = []
                real_write = project.write_zoo_project

                def record_worker_and_write(root, zoo):
                    worker_ids.append(threading.get_ident())
                    real_write(root, zoo)

                with patch("zookeep.project.write_zoo_project", side_effect=record_worker_and_write):
                    runtime.post_event({"type": "SAVE_REQUESTED", "fields": fields})
                    while True:
                        snapshot = runtime.queues["outbox"].get(timeout=3)
                        if snapshot["state"]["status-kind"] == "success":
                            break
                snapshot["state"]["fields"]["name"] = "changed detached copy"
                self.assertEqual(core.g["fields"]["name"], "Notes")
                self.assertNotEqual(worker_ids[0], threading.get_ident())
                self.assertNotIn("python", project.read_zoo_project(root))
            finally:
                runtime.post_event({"type": "CLOSE_REQUESTED"})
                runtime.g["thread"].join(timeout=3)
                self.assertFalse(runtime.g["thread"].is_alive())

    def test_cli_setup_failure_surfaces_and_stops_worker(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "unsupported"):
                runtime.run_setup_command(Path(directory))
            self.assertFalse(runtime.g["thread"].is_alive())

    def test_save_and_setup_effects_run_in_order_and_close_waits_for_completion(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entered = threading.Event()
            release = threading.Event()

            def wait_for_pending_setup_to_be_released(target):
                self.assertEqual(project.read_zoo_project(target)["name"], "Notes")
                entered.set()
                if not release.wait(timeout=3):
                    raise RuntimeError("Test did not release pending setup")

            runtime.start_runtime(root)
            try:
                loaded = runtime.queues["outbox"].get(timeout=3)
                fields = dict(loaded["state"]["fields"], name="Notes")
                fields.update({"repo-type": "basic-2026", "repository.name": "notes"})
                with patch("zookeep.setup.run_setup", side_effect=wait_for_pending_setup_to_be_released):
                    runtime.post_event({"type": "SAVE_AND_SETUP_REQUESTED", "fields": fields})
                    self.assertTrue(entered.wait(timeout=3))
                    runtime.post_event({"type": "CLOSE_REQUESTED"})
                    self.assertTrue(runtime.g["thread"].is_alive())
                    release.set()
                    runtime.g["thread"].join(timeout=3)
                    self.assertFalse(runtime.g["thread"].is_alive())
                    states = []
                    while not runtime.queues["outbox"].empty():
                        states.append(runtime.queues["outbox"].get()["state"])
                    self.assertIn("Setup complete", states[-2]["status"])
                    self.assertEqual(states[-1]["phase"], "closed")
            finally:
                release.set()
                if runtime.g["thread"].is_alive():
                    runtime.post_event({"type": "CLOSE_REQUESTED"})
                    runtime.g["thread"].join(timeout=3)
