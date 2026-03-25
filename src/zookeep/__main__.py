import datetime
import json
import re
import subprocess
from pathlib import Path

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


# -- zoo-project.json --

def read_zoo_project(root):
    """Read zoo-project.json if present; return dict or empty dict."""
    p = root / "zoo-project.json"
    if not p.is_file():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


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


def inspect_git(root):
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root, capture_output=True, check=True
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return {"is-repo": False, "has-upstream": False, "has-github-upstream": False}

    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root, capture_output=True, text=True, check=True
        )
        upstream_url = result.stdout.strip()
    except subprocess.CalledProcessError:
        return {"is-repo": True, "has-upstream": False, "has-github-upstream": False}

    has_github = "github.com" in upstream_url
    return {"is-repo": True, "has-upstream": True, "has-github-upstream": has_github, "upstream-url": upstream_url}


def inspect_registry():
    registry_path_str = app.ctx["registry.path"]
    if not registry_path_str:
        return {"configured": False, "exists": False}
    p = Path(registry_path_str).expanduser().resolve()
    return {"configured": True, "exists": p.is_file()}


# -- init-git helpers --

def create_gitignore_if_missing(root):
    p = root / ".gitignore"
    if not p.is_file():
        p.write_text(DEFAULT_GITIGNORE, encoding="utf-8")
        print("Created: .gitignore")


def create_readme_if_missing(root, name):
    p = root / "README.md"
    if not p.is_file():
        p.write_text(f"# {name}\n", encoding="utf-8")
        print("Created: README.md")


def create_license_if_missing(root, zoo):
    p = root / "LICENSE"
    if p.is_file():
        return
    license_id = zoo.get("license", "")
    if not license_id:
        return
    year = datetime.date.today().year
    if license_id == "CC0-1.0":
        p.write_text(LICENSE_CC0, encoding="utf-8")
        print("Created: LICENSE (CC0-1.0)")
    elif license_id == "MIT":
        author = get_git_user_name(root)
        p.write_text(LICENSE_MIT.format(year=year, author=author), encoding="utf-8")
        print(f"Created: LICENSE (MIT, {year} {author})")
    else:
        print(f"Warning: unknown license '{license_id}' -- LICENSE not created.")


def get_git_user_name(root):
    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            cwd=root, capture_output=True, text=True, check=True
        )
        return result.stdout.strip() or "Unknown Author"
    except subprocess.CalledProcessError:
        return "Unknown Author"


def is_git_repo(root):
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=root, capture_output=True, check=True
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


# -- commands --

def cmd_clean():
    root = app.get_path("zookeeper-report.json", "e").parent
    report_path = root / "zookeeper-report.json"
    if report_path.exists():
        report_path.unlink()
        print(f"Removed: {report_path}")
    else:
        print("Nothing to clean.")


def cmd_inspect():
    root = app.get_path("zookeeper-report.json", "e").parent

    report = {
        "project-root": str(root),
        "repository": inspect_repository(root),
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
    root = app.get_path("zookeeper-report.json", "e").parent
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
        cwd=root, capture_output=True
    )
    if result.returncode != 0:
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=root, check=True)
        print("Created initial commit.")
    else:
        print("Nothing to commit.")


def cmd_publish_github():
    root = app.get_path("zookeeper-report.json", "e").parent

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
            cwd=root
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
    app.set_flag("search_upwards_for_project_dir", True)

    app.declare_key("registry.path", "")
    app.describe_key("registry.path", "Path to registry.json (leave empty if unused).")

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
