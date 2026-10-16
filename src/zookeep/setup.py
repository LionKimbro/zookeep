"""Set up the current project in explicit stages. Owned by the core worker.

g holds the bound project; reg holds the validated packages for this run.
No Tk calls, shared cross-thread registers, or automatic commits after HEAD exists.
"""

from pathlib import Path
import shutil
import subprocess

from zookeep import project


g = {"root": None, "zoo": None}
reg = {"packages": None, "pydeck": None}


def run_setup(root):
    g.update(root=Path(root).resolve(), zoo=project.read_zoo_project(root))
    reg.update(packages=[], pydeck=None)
    try:
        validate_setup_before_creating_files()
        create_project_structure_for_selected_type()
        initialize_pydeck_storage_in_project()
        initialize_git(g["root"])
    finally:
        reg.update(packages=None, pydeck=None)
        g.update(root=None, zoo=None)


def validate_setup_before_creating_files():
    root, zoo = g["root"], g["zoo"]
    if zoo.get("repo-type") not in project.PROJECT_TYPES:
        raise ValueError("Repository type unsupported presently; no setup performed.")
    if not isinstance(zoo.get("name"), str) or not zoo["name"].strip():
        raise ValueError("Project name is required in zoo-project.json.")
    reg["pydeck"] = shutil.which("pydeck26")
    if reg["pydeck"] is None:
        raise ValueError("pydeck26 is not installed or not on PATH. Install it, then rerun setup.")
    if shutil.which("git") is None:
        raise ValueError("Git is not installed or not on PATH.")
    if project.repo_type_requires_python(zoo):
        if not project.get_python_distribution_name(zoo):
            raise ValueError("python.distribution.name is required. Run zookeep doctor or edit the JSON.")
        packages = zoo.get("python", {}).get("import-packages")
        normalized = project.get_python_import_packages(zoo)
        if not normalized or not isinstance(packages, list) or len(packages) != len(normalized):
            raise ValueError("python.import-packages must contain valid name/path records.")
        for package in normalized:
            path = (root / package["path"]).resolve()
            if Path(package["path"]).is_absolute() or root not in path.parents:
                raise ValueError(f"Unsafe import-package path: {package['path']}")
        reg["packages"] = normalized
        # Check TOML before setup creates or commits anything.
        project.read_pyproject_document(root)


def create_project_structure_for_selected_type():
    root, zoo = g["root"], g["zoo"]
    (root / "db").mkdir(exist_ok=True)
    project.create_gitignore_if_missing(root)
    project.write_zoo_project(root, zoo)
    if not project.repo_type_requires_python(zoo):
        return
    raw = root / "docs" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    if not any(raw.iterdir()):
        project.create_file_if_missing(raw / ".gitkeep")
    for package in reg["packages"]:
        project.create_file_if_missing(root / package["path"] / "__init__.py")
    result = project.reconcile_pyproject(root, zoo)
    if result.get("error"):
        raise ValueError(result["error"])
    project.create_readme_if_missing(root, project.get_repo_name(root, zoo))
    project.create_license_if_missing(root, zoo)


def initialize_pydeck_storage_in_project():
    result = subprocess.run(
        [reg["pydeck"], "init"], cwd=g["root"],
        capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"pydeck26 init failed: {result.stderr.strip() or result.stdout.strip()}")
    print(result.stdout.strip())


def run_git(root, args):
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, timeout=60,
    )
    if result.returncode:
        raise RuntimeError(f"Git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def has_local_repository(root):
    # A parent repo is not this project's repository. Worktrees have a .git file.
    return (root / ".git").exists()


def has_commit(root):
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "HEAD"],
        capture_output=True, text=True, timeout=60,
    )
    return result.returncode == 0


def initialize_git(root):
    root = Path(root).resolve()
    if not has_local_repository(root):
        run_git(root, ["init"])
        print("Initialized project Git repository.")
    if has_commit(root):
        print("Git repository already has commits; index and history left unchanged.")
        return
    # Exclude local tool state even if the project already had a .gitignore.
    exclude_path = Path(run_git(root, ["rev-parse", "--git-path", "info/exclude"]))
    if not exclude_path.is_absolute():
        exclude_path = root / exclude_path
    exclude_path.parent.mkdir(parents=True, exist_ok=True)
    contents = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    excludes = ["/.zookeep/", "/.pydeck26/", "/zookeeper-report.json"]
    missing = [pattern for pattern in excludes if pattern not in contents.splitlines()]
    if missing:
        exclude_path.write_text(contents + "\n" + "\n".join(missing) + "\n", encoding="utf-8")
    run_git(root, ["add", "--all", "--", "."])
    staged = run_git(root, ["diff", "--cached", "--name-only"])
    if not staged:
        print("No files to include in an initial commit.")
        return
    run_git(root, ["commit", "-m", "Initial commit"])
    print("Created initial commit.")
