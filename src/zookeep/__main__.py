import datetime
import json
import re
import subprocess
import tkinter as tk
import uuid
from pathlib import Path
from tkinter import ttk

import lionscliapp as app


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
INIT_FIELD_SPECS = [
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
        "kind": "entry",
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
        "name": "python-package.name",
        "label": "Python Package Name",
        "kind": "entry",
        "default": "",
        "required": True,
    },
]


# -- zoo-project.json --

def get_project_root():
    return app.get_path("zookeeper-report.json", "e").parent


def get_zoo_project_path(root):
    return root / ZOO_PROJECT_FILE


def has_zoo_project(root):
    return get_zoo_project_path(root).is_file()


def read_zoo_project(root):
    """Read zoo-project.json if present; return dict or empty dict."""
    path = get_zoo_project_path(root)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def make_init_zoo_project(form_data):
    """Normalize GUI form data into canonical zoo-project content."""
    return {
        "name": form_data["name"],
        "repo-type": form_data["repo-type"],
        "license": form_data["license"],
        "repository": {
            "name": form_data["repository.name"],
            "visibility": form_data["repository.visibility"],
        },
        "python-package": {
            "name": form_data["python-package.name"],
        },
    }


def zoo_project_has_guid(zoo):
    return ZOO_GUID_KEY in zoo


def zoo_project_guid_is_first(zoo):
    if not zoo_project_has_guid(zoo):
        return False
    return next(iter(zoo)) == ZOO_GUID_KEY


def repo_type_requires_python_package(zoo):
    return zoo.get("repo-type") == "python-2026-03"


def get_python_package_name(zoo):
    python_package = zoo.get("python-package")
    if not isinstance(python_package, dict):
        return None
    name = python_package.get("name")
    if not isinstance(name, str):
        return None
    name = name.strip()
    if not name:
        return None
    return name


def zoo_project_has_python_package_name(zoo):
    return get_python_package_name(zoo) is not None


def ensure_python_package_placeholder(zoo):
    python_package = zoo.get("python-package")
    if not isinstance(python_package, dict):
        zoo["python-package"] = {"name": None}
        return True

    if "name" not in python_package or python_package["name"] == "":
        python_package["name"] = None
        return True

    return False


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
            "python-package-required": False,
            "has-python-package-name": False,
            "python-package-name": None,
        }

    zoo = read_zoo_project(root)
    python_package_required = repo_type_requires_python_package(zoo)
    return {
        "exists": True,
        "has-guid": zoo_project_has_guid(zoo),
        "guid-is-first": zoo_project_guid_is_first(zoo),
        "python-package-required": python_package_required,
        "has-python-package-name": zoo_project_has_python_package_name(zoo),
        "python-package-name": get_python_package_name(zoo),
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


def inspect_registry():
    registry_path_str = app.ctx["registry.path"]
    if not registry_path_str:
        return {"configured": False, "exists": False}
    path = Path(registry_path_str).expanduser().resolve()
    return {"configured": True, "exists": path.is_file()}


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


# -- init ui --

def show_init_form(root_path):
    """Open the tkinter init form and return normalized form data or None."""
    state = {"values": None}
    window = tk.Tk()
    window.title(f"zookeep init - {root_path.name}")
    window.resizable(False, False)

    frame = ttk.Frame(window, padding=16)
    frame.grid(row=0, column=0, sticky="nsew")

    widgets = {}
    message_var = tk.StringVar(value="")

    for row, spec in enumerate(INIT_FIELD_SPECS):
        ttk.Label(frame, text=spec["label"]).grid(
            row=row,
            column=0,
            sticky="w",
            padx=(0, 12),
            pady=6,
        )
        value_var = tk.StringVar(value=spec["default"])
        if spec["kind"] == "choice":
            widget = ttk.Combobox(
                frame,
                textvariable=value_var,
                values=spec["choices"],
                state="readonly",
                width=24,
            )
        else:
            widget = ttk.Entry(frame, textvariable=value_var, width=28)
        widget.grid(row=row, column=1, sticky="ew", pady=6)
        widgets[spec["name"]] = {
            "spec": spec,
            "widget": widget,
            "var": value_var,
        }

    def handle_cancel():
        window.destroy()

    def handle_save():
        form_data = {}
        for name, info in widgets.items():
            value = info["var"].get().strip()
            if info["spec"]["required"] and not value:
                message_var.set(f"{info['spec']['label']} is required.")
                info["widget"].focus_set()
                return
            form_data[name] = value
        state["values"] = form_data
        window.destroy()

    button_row = len(INIT_FIELD_SPECS)
    ttk.Label(frame, textvariable=message_var, foreground="#8b0000").grid(
        row=button_row,
        column=0,
        columnspan=2,
        sticky="w",
        pady=(6, 0),
    )
    buttons = ttk.Frame(frame)
    buttons.grid(row=button_row + 1, column=0, columnspan=2, sticky="e", pady=(12, 0))
    ttk.Button(buttons, text="Save", command=handle_save).grid(row=0, column=0, padx=(0, 8))
    ttk.Button(buttons, text="Cancel", command=handle_cancel).grid(row=0, column=1)

    widgets["name"]["widget"].focus_set()
    window.protocol("WM_DELETE_WINDOW", handle_cancel)
    window.mainloop()
    return state["values"]


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


# -- commands --

def cmd_init():
    root = get_project_root()

    if has_zoo_project(root):
        print("zoo-project.json already exists.")
        return

    form_data = show_init_form(root)
    if form_data is None:
        print("Cancelled.")
        return

    zoo = make_init_zoo_project(form_data)
    write_zoo_project(root, zoo)
    print(f"Created: {get_zoo_project_path(root)}")


def cmd_doctor():
    root = get_project_root()

    if not has_zoo_project(root):
        print("zoo-project.json is missing.")
        return

    zoo = read_zoo_project(root)
    messages = []
    changed = False

    if not zoo_project_has_guid(zoo):
        messages.append("GUID missing. Added new zookeep-project-guid.")
        changed = True

    if repo_type_requires_python_package(zoo) and not zoo_project_has_python_package_name(zoo):
        candidates = find_python_package_candidates(root)
        if len(candidates) == 1:
            python_package = zoo.get("python-package")
            if not isinstance(python_package, dict):
                zoo["python-package"] = {"name": candidates[0]}
            else:
                python_package["name"] = candidates[0]
            messages.append(f"python-package.name missing. Repaired from existing src/{candidates[0]} package.")
        else:
            ensure_python_package_placeholder(zoo)
            if len(candidates) > 1:
                messages.append("python-package.name missing. Multiple src packages found. Added null placeholder. Please update zoo-project.json.")
            else:
                messages.append("python-package.name missing. Added null placeholder. Please update zoo-project.json.")
        changed = True

    if changed:
        write_zoo_project(root, zoo)
        for message in messages:
            print(message)
        return

    if not zoo_project_guid_is_first(zoo):
        write_zoo_project(root, zoo)
        print("GUID present. Moved zookeep-project-guid to first key.")
        return

    print("GUID present.")


def cmd_setup():
    root = get_project_root()
    zoo = read_zoo_project(root)
    created_any = False

    if create_directory_if_missing(root / "docs"):
        print("Created: docs")
        created_any = True

    if create_directory_if_missing(root / "docs" / "raw"):
        print("Created: docs/raw")
        created_any = True

    if repo_type_requires_python_package(zoo):
        package_name = get_python_package_name(zoo)
        if package_name is None:
            print("python-package.name is missing in zoo-project.json. Update it before creating src package directory.")
        else:
            package_path = root / "src" / package_name
            if create_directory_if_missing(package_path):
                print(f"Created: src/{package_name}")
                created_any = True
            init_path = package_path / "__init__.py"
            if create_file_if_missing(init_path):
                print(f"Created: src/{package_name}/__init__.py")
                created_any = True

    if not created_any:
        print("Nothing to set up.")


def cmd_clean():
    root = get_project_root()
    report_path = root / "zookeeper-report.json"
    if report_path.exists():
        report_path.unlink()
        print(f"Removed: {report_path}")
    else:
        print("Nothing to clean.")


def cmd_inspect():
    root = get_project_root()

    report = {
        "project-root": str(root),
        "repository": inspect_repository(root),
        "zoo-project": inspect_zoo_project(root),
        "git": inspect_git(root),
        "docs": inspect_docs(root),
        "gitignore": inspect_gitignore(root),
        "dot-directories": inspect_dot_directories(root),
        "registry": inspect_registry(),
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    report_path = root / "zookeeper-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report written to: {report_path}")


def cmd_init_git():
    root = get_project_root()
    zoo = read_zoo_project(root)
    name = get_repo_name(root, zoo)

    if is_git_repo(root):
        print("Git repository already exists.")
    else:
        subprocess.run(["git", "init"], cwd=root, check=True)
        print("Initialized git repository.")

    create_gitignore_if_missing(root)
    create_readme_if_missing(root, name)
    create_license_if_missing(root, zoo)

    subprocess.run(["git", "add", "."], cwd=root, check=True)
    result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=root,
        capture_output=True,
    )
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=root, check=True)
        print("Created initial commit.")
    else:
        print("Nothing to commit.")


def cmd_publish_github():
    root = get_project_root()

    if not is_git_repo(root):
        print("No git repository found. Run 'zookeep init-git' first.")
        return

    zoo = read_zoo_project(root)
    name = get_repo_name(root, zoo)
    visibility = zoo.get("repository", {}).get("visibility", "public")

    print(f"Publishing '{name}' to GitHub ({visibility})...")
    flag = f"--{visibility}"
    try:
        result = subprocess.run(
            ["gh", "repo", "create", name, flag, "--source=.", "--remote=origin", "--push"],
            cwd=root,
        )
    except FileNotFoundError:
        print("'gh' CLI not found. Install it from https://cli.github.com/ and try again.")
        return
    if result.returncode != 0:
        print("GitHub publish failed. Check 'gh' CLI authentication and try again.")
    else:
        print("Published.")


# -- setup & entry --

def _setup():
    app.declare_app("zookeep", "0.1")
    app.describe_app("Inspect and tend software project ecologies.")
    app.declare_projectdir(".zookeep")

    app.declare_key("registry.path", "")
    app.describe_key("registry.path", "Path to registry.json (leave empty if unused).")

    app.declare_cmd("init", cmd_init)
    app.describe_cmd("init", "Create zoo-project.json through a tkinter form.")

    app.declare_cmd("doctor", cmd_doctor)
    app.describe_cmd("doctor", "Inspect zoo-project.json and repair a missing GUID or python-package placeholder.")

    app.declare_cmd("setup", cmd_setup)
    app.describe_cmd("setup", "Create docs/raw and repo-type-specific starter directories.")

    app.declare_cmd("clean", cmd_clean)
    app.describe_cmd("clean", "Remove zookeep-generated artifacts (zookeeper-report.json).")

    app.declare_cmd("inspect", cmd_inspect)
    app.describe_cmd("inspect", "Inspect the local project ecology and write zookeeper-report.json.")

    app.declare_cmd("init-git", cmd_init_git)
    app.describe_cmd("init-git", "Initialize a git repository and create missing standard files.")

    app.declare_cmd("publish-github", cmd_publish_github)
    app.describe_cmd("publish-github", "Publish the local repository to GitHub.")


def _entry():
    _setup()
    app.main()


if __name__ == "__main__":
    _entry()
