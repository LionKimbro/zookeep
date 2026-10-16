"""Portable project metadata, inspection, and file helpers; no GUI state."""

import datetime
import json
import re
import subprocess
import uuid
from collections.abc import Mapping
from pathlib import Path

import tomlkit


# -- templates --

DEFAULT_GITIGNORE = """\
__pycache__/
*.py[cod]
*.egg-info/
dist/
build/
.eggs/
*.egg
.env
venv/
.venv/
.local/
.claude/
.focus-explorer/
.pycard/
.zookeep/
.pydeck26/
zookeeper-report.json
"""

LICENSE_MIT = """\
MIT License

Copyright (c) {year} {author}

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

LICENSE_CC0 = """\
CC0 1.0 Universal

This work is dedicated to the public domain under the Creative Commons CC0 1.0
Universal Public Domain Dedication.

To the extent possible under law, the author(s) have waived all copyright and
related or neighboring rights to this work.

See https://creativecommons.org/publicdomain/zero/1.0/ for details.
"""

ZOO_PROJECT_FILE = "zoo-project.json"
ZOO_GUID_KEY = "zookeep-project-guid"
PROJECT_TYPES = {
    "basic-2026": "db/, zoo-project.json, Git setup and initial commit; pydeck26 init (adds docs/whiteboard/).",
    "python-2026-03": "db/, docs/raw/, Python import packages, pyproject.toml, README, license, Git setup and initial commit; pydeck26 init.",
}
SPEC_FIELD_SPECS = [
    {
        "name": "name",
        "label": "Project Name",
        "kind": "entry",
        "default": "",
        "required": True,
    },
    {
        "name": "repo-type",
        "label": "Repository Type",
        "kind": "editable-choice",
        "choices": list(PROJECT_TYPES),
        "default": "python-2026-03",
        "required": True,
    },
    {
        "name": "license",
        "label": "License",
        "kind": "entry",
        "default": "CC0-1.0",
        "required": True,
    },
    {
        "name": "repository.name",
        "label": "Repository Name",
        "kind": "entry",
        "default": "",
        "required": True,
    },
    {
        "name": "repository.visibility",
        "label": "Visibility",
        "kind": "choice",
        "choices": ["public", "private"],
        "default": "public",
        "required": True,
    },
    {
        "name": "python.distribution.name",
        "label": "Python Distribution Name (pip install)",
        "kind": "entry",
        "default": "",
        "required": True,
    },
    {
        "name": "python.import-package.name",
        "label": "Primary Python Import Package (import)",
        "kind": "entry",
        "default": "",
        "required": True,
    },
]


# -- zoo-project.json --

def get_zoo_project_path(root):
    return root / ZOO_PROJECT_FILE


def has_zoo_project(root):
    return get_zoo_project_path(root).is_file()


def read_zoo_project(root):
    """Read zoo-project.json if present; return dict or empty dict."""
    path = get_zoo_project_path(root)
    if not path.is_file():
        return {}
    zoo = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(zoo, dict):
        raise ValueError("zoo-project.json must contain a JSON object.")
    return zoo


def write_text_atomic(path, text):
    """Atomically replace a text file with UTF-8 content."""
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(path)


def make_zoo_project_with_guid_first(zoo, guid=None):
    """Return zoo-project data with the GUID field first."""
    guid_value = guid or zoo.get(ZOO_GUID_KEY) or str(uuid.uuid4())
    updated = {ZOO_GUID_KEY: guid_value}
    for key, value in zoo.items():
        if key != ZOO_GUID_KEY:
            updated[key] = value
    return updated


def write_zoo_project(root, zoo):
    """Write zoo-project.json with stable formatting and GUID first."""
    path = get_zoo_project_path(root)
    prepared = make_zoo_project_with_guid_first(zoo)
    text = json.dumps(prepared, indent=2) + "\n"
    write_text_atomic(path, text)


def get_spec_form_values(zoo):
    repository = zoo.get("repository")
    if not isinstance(repository, dict):
        repository = {}
    primary_import = get_python_import_packages(zoo)
    primary_import_name = primary_import[0]["name"] if primary_import else ""
    return {
        "name": zoo.get("name", ""),
        "repo-type": zoo.get("repo-type", "python-2026-03"),
        "license": zoo.get("license", "CC0-1.0"),
        "repository.name": repository.get("name", ""),
        "repository.visibility": repository.get("visibility", "public"),
        "python.distribution.name": get_python_distribution_name(zoo) or "",
        "python.import-package.name": primary_import_name,
    }


def make_spec_zoo_project(form_data, existing=None):
    """Apply GUI form data while preserving identity and unedited extensions."""
    zoo = dict(existing or {})
    zoo["name"] = form_data["name"]
    zoo["repo-type"] = form_data["repo-type"]
    if repo_type_requires_python(zoo) and form_data.get("license"):
        zoo["license"] = form_data["license"]

    repository = zoo.get("repository")
    repository = dict(repository) if isinstance(repository, dict) else {}
    repository["name"] = form_data["repository.name"]
    repository["visibility"] = form_data["repository.visibility"]
    zoo["repository"] = repository

    if not repo_type_requires_python(zoo):
        return zoo

    python_config = zoo.get("python")
    python_config = dict(python_config) if isinstance(python_config, dict) else {}
    distribution = python_config.get("distribution")
    distribution = dict(distribution) if isinstance(distribution, dict) else {}
    distribution["name"] = form_data["python.distribution.name"]
    python_config["distribution"] = distribution

    existing_packages = python_config.get("import-packages")
    additional_packages = existing_packages[1:] if isinstance(existing_packages, list) else []
    primary_name = form_data["python.import-package.name"]
    primary = {}
    if isinstance(existing_packages, list) and existing_packages and isinstance(existing_packages[0], dict):
        primary.update(existing_packages[0])
    if primary.get("name") != primary_name:
        primary.update(make_import_package_record(primary_name))
    else:
        primary.setdefault("path", make_import_package_record(primary_name)["path"])
    python_config["import-packages"] = [
        primary,
        *additional_packages,
    ]
    zoo["python"] = python_config
    zoo.pop("python-package", None)
    return zoo


def zoo_project_has_guid(zoo):
    return ZOO_GUID_KEY in zoo


def zoo_project_guid_is_first(zoo):
    if not zoo_project_has_guid(zoo):
        return False
    return next(iter(zoo)) == ZOO_GUID_KEY


def repo_type_requires_python(zoo):
    return zoo.get("repo-type") == "python-2026-03"


def get_python_distribution_name(zoo):
    python_config = zoo.get("python")
    if not isinstance(python_config, dict):
        return None
    distribution = python_config.get("distribution")
    if not isinstance(distribution, dict):
        return None
    name = distribution.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    return name or None


def get_python_import_packages(zoo):
    python_config = zoo.get("python")
    if not isinstance(python_config, dict):
        return []
    packages = python_config.get("import-packages")
    if not isinstance(packages, list):
        return []

    normalized = []
    for package in packages:
        if not isinstance(package, dict):
            continue
        name = package.get("name")
        path = package.get("path")
        if not isinstance(name, str) or not name.strip():
            continue
        if not isinstance(path, str) or not path.strip():
            continue
        normalized.append({"name": name.strip(), "path": path.strip()})
    return normalized


def get_legacy_python_package_name(zoo):
    python_package = zoo.get("python-package")
    if not isinstance(python_package, dict):
        return None
    name = python_package.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def directory_contains_python_code(path):
    if not path.is_dir():
        return False
    return any(child.is_file() and child.suffix == ".py" for child in path.rglob("*.py"))


def find_python_package_candidates(root):
    src_dir = root / "src"
    if not src_dir.is_dir():
        return []

    candidates = []
    for child in sorted(src_dir.iterdir(), key=lambda p: p.name):
        if directory_contains_python_code(child):
            candidates.append(child.name)
    return candidates


def read_pyproject_document(root):
    path = root / "pyproject.toml"
    if not path.is_file():
        return None
    return tomlkit.parse(path.read_text(encoding="utf-8"))


def read_pyproject_distribution_name(root):
    try:
        document = read_pyproject_document(root)
    except (OSError, tomlkit.exceptions.ParseError):
        return None
    if document is None:
        return None
    project = document.get("project")
    if not isinstance(project, Mapping):
        return None
    name = project.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    return name.strip()


def make_import_package_record(name):
    return {
        "name": name,
        "path": f"src/{name.replace('.', '/')}",
    }


def migrate_python_metadata(root, zoo):
    """Replace legacy python-package metadata with explicit Python identities."""
    python_config = zoo.get("python")
    if not isinstance(python_config, dict):
        python_config = {}
        zoo["python"] = python_config

    distribution = python_config.get("distribution")
    if not isinstance(distribution, dict):
        distribution = {}
        python_config["distribution"] = distribution
    if not isinstance(distribution.get("name"), str) or not distribution["name"].strip():
        distribution["name"] = read_pyproject_distribution_name(root)

    packages = get_python_import_packages(zoo)
    if not packages:
        legacy_name = get_legacy_python_package_name(zoo)
        candidates = find_python_package_candidates(root)
        inferred_name = legacy_name or (candidates[0] if len(candidates) == 1 else None)
        packages = [make_import_package_record(inferred_name)] if inferred_name else []
        python_config["import-packages"] = packages

    zoo.pop("python-package", None)
    return {
        "distribution-name": get_python_distribution_name(zoo),
        "import-packages": get_python_import_packages(zoo),
    }


def get_repo_name(root, zoo):
    """Determine repository name from zoo-project.json or directory name."""
    repo = zoo.get("repository", {})
    if repo.get("name"):
        return repo["name"]
    if zoo.get("name"):
        return zoo["name"]
    return root.name


# -- inspection --

def inspect_repository(root):
    return {
        "db": (root / "db").is_dir(),
        "docs": (root / "docs").is_dir(),
        "docs/raw": (root / "docs" / "raw").is_dir(),
        "src": (root / "src").is_dir(),
        "pyproject.toml": (root / "pyproject.toml").is_file(),
        "README.md": (root / "README.md").is_file(),
        ".gitignore": (root / ".gitignore").is_file(),
    }


def inspect_docs(root):
    docs_dir = root / "docs"
    if not docs_dir.is_dir():
        return {"raw-document-count": 0, "sample-files": []}
    pattern = re.compile(r"^\d{4}__.*\.json$")
    matches = sorted(f.name for f in docs_dir.rglob("*.json") if pattern.match(f.name))
    return {
        "raw-document-count": len(matches),
        "sample-files": matches[:5],
    }


def inspect_gitignore(root):
    gitignore_path = root / ".gitignore"
    if not gitignore_path.is_file():
        return {"exists": False, "zookeeper-report.json-ignored": False}
    contents = gitignore_path.read_text(encoding="utf-8")
    ignored = "zookeeper-report.json" in contents
    return {"exists": True, "zookeeper-report.json-ignored": ignored}


def inspect_dot_directories(root):
    names = [".focus-explorer", ".pycard", ".librarian2"]
    return {name: (root / name).is_dir() for name in names}


def inspect_zoo_project(root):
    if not has_zoo_project(root):
        return {
            "exists": False,
            "has-guid": False,
            "guid-is-first": False,
            "python-required": False,
            "python-distribution-name": None,
            "python-import-packages": [],
        }

    zoo = read_zoo_project(root)
    python_required = repo_type_requires_python(zoo)
    return {
        "exists": True,
        "has-guid": zoo_project_has_guid(zoo),
        "guid-is-first": zoo_project_guid_is_first(zoo),
        "python-required": python_required,
        "python-distribution-name": get_python_distribution_name(zoo),
        "python-import-packages": get_python_import_packages(zoo),
    }


def inspect_git(root):
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"is-repo": False, "has-upstream": False, "has-github-upstream": False}

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        upstream_url = result.stdout.strip()
    except subprocess.CalledProcessError:
        return {"is-repo": True, "has-upstream": False, "has-github-upstream": False}

    has_github = "github.com" in upstream_url
    return {
        "is-repo": True,
        "has-upstream": True,
        "has-github-upstream": has_github,
        "upstream-url": upstream_url,
    }


# -- init-git helpers --

def create_gitignore_if_missing(root):
    path = root / ".gitignore"
    if not path.is_file():
        path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print("Created: .gitignore")


def create_readme_if_missing(root, name):
    path = root / "README.md"
    if not path.is_file():
        path.write_text(f"# {name}\n", encoding="utf-8")
        print("Created: README.md")


def create_license_if_missing(root, zoo):
    path = root / "LICENSE"
    if path.is_file():
        return
    license_id = zoo.get("license", "")
    if not license_id:
        return
    year = datetime.date.today().year
    if license_id == "CC0-1.0":
        path.write_text(LICENSE_CC0, encoding="utf-8")
        print("Created: LICENSE (CC0-1.0)")
    elif license_id == "MIT":
        author = get_git_user_name(root)
        path.write_text(LICENSE_MIT.format(year=year, author=author), encoding="utf-8")
        print(f"Created: LICENSE (MIT, {year} {author})")
    else:
        print(f"Warning: unknown license '{license_id}' -- LICENSE not created.")


def get_git_user_name(root):
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() or "Unknown Author"
    except subprocess.CalledProcessError:
        return "Unknown Author"


def is_git_repo(root):
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root,
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# -- setup helpers --

def create_directory_if_missing(path):
    if path.is_dir():
        return False
    path.mkdir(parents=True, exist_ok=True)
    return True


def create_file_if_missing(path, text=""):
    if path.is_file():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


# -- pyproject.toml helpers --

def make_minimal_pyproject_document(distribution_name):
    document = tomlkit.document()

    build_system = tomlkit.table()
    build_system["requires"] = ["setuptools>=61.0"]
    build_system["build-backend"] = "setuptools.build_meta"
    document["build-system"] = build_system

    project = tomlkit.table()
    project["name"] = distribution_name
    project["version"] = "0.1.0"
    project["requires-python"] = ">=3.10"
    document["project"] = project

    find = tomlkit.table()
    find["where"] = ["src"]
    packages = tomlkit.table()
    packages["find"] = find
    setuptools = tomlkit.table()
    setuptools["packages"] = packages
    tool = tomlkit.table()
    tool["setuptools"] = setuptools
    document["tool"] = tool
    return document


def reconcile_pyproject(root, zoo):
    """Make the smallest TOML change needed to match the distribution name."""
    distribution_name = get_python_distribution_name(zoo)
    if distribution_name is None:
        return {
            "changed": False,
            "error": "python.distribution.name is missing in zoo-project.json.",
        }

    path = root / "pyproject.toml"
    if not path.is_file():
        document = make_minimal_pyproject_document(distribution_name)
        write_text_atomic(path, tomlkit.dumps(document))
        return {
            "changed": True,
            "created": True,
            "message": "Created minimal pyproject.toml.",
        }

    try:
        document = read_pyproject_document(root)
    except (OSError, tomlkit.exceptions.ParseError) as exc:
        return {
            "changed": False,
            "error": f"Could not parse pyproject.toml: {exc}",
        }

    project = document.get("project")
    if not isinstance(project, Mapping):
        project = tomlkit.table()
        document["project"] = project

    current_name = project.get("name")
    if current_name == distribution_name:
        return {
            "changed": False,
            "message": "pyproject.toml already matches zoo-project.json.",
        }

    project["name"] = distribution_name
    write_text_atomic(path, tomlkit.dumps(document))
    return {
        "changed": True,
        "created": False,
        "message": f"Updated pyproject.toml project.name to '{distribution_name}'.",
    }


