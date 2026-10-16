"""Integration checks use real Git repositories, never this checkout's index."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from zookeep import project, setup


def seed_project(root, repo_type="basic-2026"):
    zoo = {"name": "sample", "repo-type": repo_type, "license": "CC0-1.0"}
    if repo_type == "python-2026-03":
        zoo["python"] = {
            "distribution": {"name": "sample-dist"},
            "import-packages": [{"name": "sample_pkg", "path": "src/sample_pkg"}],
        }
    project.write_zoo_project(root, zoo)


def initialize_test_git_identity(root):
    setup.run_git(root, ["init"])
    setup.run_git(root, ["config", "user.name", "Zookeep Test"])
    setup.run_git(root, ["config", "user.email", "test@example.invalid"])


def initialize_stub_pydeck_storage():
    root = setup.g["root"]
    (root / "db" / "pydeck26").mkdir(parents=True, exist_ok=True)
    project.create_file_if_missing(root / "db" / "pydeck26" / "whiteboard.txt")
    (root / "docs" / "whiteboard").mkdir(parents=True, exist_ok=True)


class SetupTests(unittest.TestCase):
    def test_basic_setup_and_rerun_preserve_existing_index_and_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_project(root)
            initialize_test_git_identity(root)
            with patch("zookeep.setup.shutil.which", return_value="installed"), patch(
                "zookeep.setup.initialize_pydeck_storage_in_project", side_effect=initialize_stub_pydeck_storage
            ):
                setup.run_setup(root)
                self.assertTrue((root / "db" / "pydeck26").is_dir())
                for path in ["docs/raw", "src", "pyproject.toml", "README.md", "LICENSE"]:
                    self.assertFalse((root / path).exists(), path)
                head = setup.run_git(root, ["rev-parse", "HEAD"])
                (root / "work.txt").write_text("staged")
                setup.run_git(root, ["add", "work.txt"])
                (root / "work.txt").write_text("unstaged edit")
                index = setup.run_git(root, ["diff", "--cached"])
                setup.run_setup(root)
                self.assertEqual(head, setup.run_git(root, ["rev-parse", "HEAD"]))
                self.assertEqual(index, setup.run_git(root, ["diff", "--cached"]))

    def test_python_setup_commits_packaging_and_raw_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_project(root, "python-2026-03")
            initialize_test_git_identity(root)
            with patch("zookeep.setup.shutil.which", return_value="installed"), patch(
                "zookeep.setup.initialize_pydeck_storage_in_project", side_effect=initialize_stub_pydeck_storage
            ):
                setup.run_setup(root)
            tracked = setup.run_git(root, ["ls-files"])
            for path in ["docs/raw/.gitkeep", "src/sample_pkg/__init__.py", "pyproject.toml", "README.md", "LICENSE"]:
                self.assertIn(path, tracked)
            self.assertEqual(project.read_pyproject_distribution_name(root), "sample-dist")

    def test_unknown_type_missing_pydeck_and_unsafe_paths_create_nothing(self):
        for repo_type, missing, unsafe in [("custom", False, False), ("basic-2026", True, False), ("python-2026-03", False, True)]:
            with self.subTest(repo_type=repo_type), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                seed_project(root, repo_type)
                if unsafe:
                    zoo = project.read_zoo_project(root)
                    zoo["python"]["import-packages"][0]["path"] = "../escaped"
                    project.write_zoo_project(root, zoo)
                with patch("zookeep.setup.shutil.which", return_value=None if missing else "installed"):
                    with self.assertRaises(ValueError):
                        setup.run_setup(root)
                self.assertEqual([path.name for path in root.iterdir()], ["zoo-project.json"])

    def test_pydeck_failure_does_not_make_initial_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            seed_project(root)
            initialize_test_git_identity(root)
            failure = subprocess.CompletedProcess([], 1, "", "PyDeck failed")
            with patch("zookeep.setup.shutil.which", return_value="installed"), patch("zookeep.setup.subprocess.run", return_value=failure):
                with self.assertRaisesRegex(RuntimeError, "PyDeck failed"):
                    setup.run_setup(root)
            self.assertFalse(setup.has_commit(root))

    def test_new_repository_inside_parent_does_not_commit_parent_files(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            initialize_test_git_identity(parent)
            (parent / "parent.txt").write_text("parent")
            setup.run_git(parent, ["add", "."])
            root = parent / "child"
            root.mkdir()
            (root / "zoo-project.json").write_text("{}")
            # Supply identity to the new child via environment, without global config.
            with patch.dict("os.environ", {
                "GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test", "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }):
                setup.initialize_git(root)
            self.assertEqual(Path(setup.run_git(root, ["rev-parse", "--show-toplevel"])).resolve(), root.resolve())
            self.assertFalse(setup.has_commit(parent))
            self.assertEqual(setup.run_git(parent, ["diff", "--cached", "--name-only"]), "parent.txt")

    def test_pydeck_subprocess_runs_in_target_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            setup.g["root"] = root
            setup.reg["pydeck"] = "pydeck26.exe"
            try:
                with patch("zookeep.setup.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "Initialized", "")) as run:
                    setup.initialize_pydeck_storage_in_project()
                    self.assertEqual(run.call_args.args[0], ["pydeck26.exe", "init"])
                    self.assertEqual(run.call_args.kwargs["cwd"], root)
            finally:
                setup.g["root"] = None
                setup.reg["pydeck"] = None
