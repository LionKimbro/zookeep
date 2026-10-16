"""LionsCLIApp declarations and thin command adapters."""

import datetime
import json
from pathlib import Path
import subprocess

import lionscliapp as app

from zookeep.project import (
    has_zoo_project, read_zoo_project,
    write_zoo_project, zoo_project_has_guid, zoo_project_guid_is_first,
    repo_type_requires_python, migrate_python_metadata, reconcile_pyproject,
    inspect_repository, inspect_zoo_project, inspect_git, inspect_docs,
    inspect_gitignore, inspect_dot_directories, is_git_repo, get_repo_name,
)


def get_project_root():
    return app.get_path("zookeeper-report.json", "e").parent


def inspect_registry():
    registry_path = app.ctx["registry.path"]
    if not registry_path:
        return {"configured": False, "exists": False}
    return {"configured": True, "exists": Path(registry_path).expanduser().is_file()}


# -- commands --

def cmd_spec():
    from zookeep import tk
    tk.run_editor(get_project_root())


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

    if repo_type_requires_python(zoo):
        before_python = json.dumps(zoo, sort_keys=True)
        migration = migrate_python_metadata(root, zoo)
        if json.dumps(zoo, sort_keys=True) != before_python:
            changed = True
            messages.append("Migrated Python metadata to explicit distribution and import-package fields.")
        if migration["distribution-name"] is None:
            messages.append("python.distribution.name is unresolved. Update zoo-project.json.")
        if not migration["import-packages"]:
            messages.append("python.import-packages is empty. Update zoo-project.json.")

    if changed:
        write_zoo_project(root, zoo)
    elif not zoo_project_guid_is_first(zoo):
        write_zoo_project(root, zoo)
        messages.append("GUID present. Moved zookeep-project-guid to first key.")

    if messages:
        for message in messages:
            print(message)
        return

    print("zoo-project.json is healthy.")


def cmd_doctor_pyproject():
    root = get_project_root()
    if not has_zoo_project(root):
        print("zoo-project.json is missing.")
        return

    zoo = read_zoo_project(root)
    if not repo_type_requires_python(zoo):
        print("This repository type does not define Python project metadata.")
        return

    result = reconcile_pyproject(root, zoo)
    if result.get("error"):
        print(result["error"])
        return
    print(result["message"])


def cmd_setup():
    from zookeep import runtime
    runtime.run_setup_command(get_project_root())


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
    from zookeep import setup
    setup.initialize_git(get_project_root())


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

    app.declare_cmd("spec", cmd_spec)
    app.describe_cmd("spec", "Create or edit zoo-project.json through a tkinter form.")

    app.declare_cmd("doctor", cmd_doctor)
    app.describe_cmd("doctor", "Inspect zoo-project.json and migrate or repair project metadata.")

    app.declare_cmd("doctor-pyproject", cmd_doctor_pyproject)
    app.describe_cmd("doctor-pyproject", "Create or minimally reconcile pyproject.toml with zoo-project.json.")

    app.declare_cmd("setup", cmd_setup)
    app.describe_cmd("setup", "Set up basic-2026 or python-2026-03, initialize PyDeck, and create an initial Git commit.")

    app.declare_cmd("clean", cmd_clean)
    app.describe_cmd("clean", "Remove zookeep-generated artifacts (zookeeper-report.json).")

    app.declare_cmd("inspect", cmd_inspect)
    app.describe_cmd("inspect", "Inspect the local project ecology and write zookeeper-report.json.")

    app.declare_cmd("init-git", cmd_init_git)
    app.describe_cmd("init-git", "Ensure a project-local Git repository and commit only when it has no commits.")

    app.declare_cmd("publish-github", cmd_publish_github)
    app.describe_cmd("publish-github", "Publish the local repository to GitHub.")


def _entry():
    _setup()
    app.main()


if __name__ == "__main__":
    _entry()
