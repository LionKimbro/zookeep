import tempfile
import unittest
from pathlib import Path

import tomlkit

from zookeep import __main__ as zookeep


class ProjectMetadataTests(unittest.TestCase):
    def test_spec_keeps_distribution_and_import_names_distinct(self):
        zoo = zookeep.make_spec_zoo_project(
            {
                "name": "Aspect Slicer",
                "repo-type": "python-2026-03",
                "license": "CC0-1.0",
                "repository.name": "aspect-slicer",
                "repository.visibility": "public",
                "python.distribution.name": "aspect-slicer",
                "python.import-package.name": "aspect_slicer",
            }
        )

        self.assertEqual(zoo["name"], "Aspect Slicer")
        self.assertEqual(zoo["repository"]["name"], "aspect-slicer")
        self.assertEqual(zoo["python"]["distribution"]["name"], "aspect-slicer")
        self.assertEqual(
            zoo["python"]["import-packages"],
            [{"name": "aspect_slicer", "path": "src/aspect_slicer"}],
        )

    def test_spec_edit_preserves_guid_extensions_and_additional_imports(self):
        existing = {
            "zookeep-project-guid": "fixed-guid",
            "name": "Old Name",
            "repo-type": "python-2026-03",
            "license": "MIT",
            "repository": {
                "name": "old-repo",
                "visibility": "private",
                "host": "github",
            },
            "python": {
                "distribution": {"name": "old-dist", "index": "pypi"},
                "import-packages": [
                    {"name": "old_import", "path": "src/old_import"},
                    {"name": "extra_import", "path": "src/extra_import"},
                ],
            },
            "extension-field": {"preserve": True},
        }
        form_data = {
            "name": "New Name",
            "repo-type": "python-2026-03",
            "license": "CC0-1.0",
            "repository.name": "new-repo",
            "repository.visibility": "public",
            "python.distribution.name": "new-dist",
            "python.import-package.name": "new_import",
        }

        zoo = zookeep.make_spec_zoo_project(form_data, existing)

        self.assertEqual(zoo["zookeep-project-guid"], "fixed-guid")
        self.assertEqual(zoo["extension-field"], {"preserve": True})
        self.assertEqual(zoo["repository"]["host"], "github")
        self.assertEqual(zoo["python"]["distribution"]["index"], "pypi")
        self.assertEqual(
            zoo["python"]["import-packages"],
            [
                {"name": "new_import", "path": "src/new_import"},
                {"name": "extra_import", "path": "src/extra_import"},
            ],
        )

    def test_doctor_migrates_legacy_python_metadata(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "image-essentializer"\n',
                encoding="utf-8",
            )
            zoo = {
                "repo-type": "python-2026-03",
                "python-package": {"name": "imgess"},
            }

            result = zookeep.migrate_python_metadata(root, zoo)

            self.assertNotIn("python-package", zoo)
            self.assertEqual(result["distribution-name"], "image-essentializer")
            self.assertEqual(
                result["import-packages"],
                [{"name": "imgess", "path": "src/imgess"}],
            )

    def test_reconcile_existing_pyproject_preserves_unrelated_content(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "pyproject.toml"
            path.write_text(
                "# keep this comment\n"
                "[project]\n"
                'name = "old-name"\n'
                'version = "7.4.2"\n'
                'dependencies = ["example"]\n\n'
                "[tool.example]\n"
                "enabled = true\n",
                encoding="utf-8",
            )
            zoo = {
                "python": {
                    "distribution": {"name": "new-name"},
                    "import-packages": [],
                }
            }

            result = zookeep.reconcile_pyproject(root, zoo)
            updated = path.read_text(encoding="utf-8")

            self.assertTrue(result["changed"])
            self.assertIn("# keep this comment", updated)
            self.assertIn('name = "new-name"', updated)
            self.assertIn('version = "7.4.2"', updated)
            self.assertIn('dependencies = ["example"]', updated)
            self.assertIn("[tool.example]", updated)
            self.assertIn("enabled = true", updated)

    def test_reconcile_creates_minimal_pyproject_when_missing(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            zoo = {
                "python": {
                    "distribution": {"name": "sample-distribution"},
                    "import-packages": [
                        {"name": "sample_import", "path": "src/sample_import"}
                    ],
                }
            }

            result = zookeep.reconcile_pyproject(root, zoo)
            document = tomlkit.parse(
                (root / "pyproject.toml").read_text(encoding="utf-8")
            )

            self.assertTrue(result["created"])
            self.assertEqual(document["project"]["name"], "sample-distribution")
            self.assertEqual(document["project"]["version"], "0.1.0")
            self.assertEqual(
                list(document["tool"]["setuptools"]["packages"]["find"]["where"]),
                ["src"],
            )

    def test_reconcile_does_not_overwrite_invalid_toml(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = root / "pyproject.toml"
            original = '[project\nname = "broken"\n'
            path.write_text(original, encoding="utf-8")
            zoo = {
                "python": {
                    "distribution": {"name": "new-name"},
                    "import-packages": [],
                }
            }

            result = zookeep.reconcile_pyproject(root, zoo)

            self.assertIn("error", result)
            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
