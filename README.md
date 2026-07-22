# zookeep

A system for helping software projects come into being as repositories and keeping them healthy over time.

## Usage

```
zookeep spec
zookeep doctor
zookeep doctor-pyproject
zookeep setup
zookeep inspect
```

`zookeep spec` opens a tkinter form that creates or edits `zoo-project.json` in the current project root. Existing values are prefilled. For Python repositories it separately records the distribution name used by `pip install` and the primary import-package name used by `import`.

`zookeep doctor` checks `zoo-project.json`, repairs a missing `zookeep-project-guid`, and migrates legacy `python-package.name` data into explicit `python.distribution` and `python.import-packages` metadata.

`zookeep doctor-pyproject` creates a minimal setuptools/src-layout `pyproject.toml` when it is absent. When it already exists, the command preserves its content and changes only `[project].name` when needed to match `python.distribution.name` in `zoo-project.json`.

`zookeep setup` creates `docs/`, `docs/raw/`, and the paths listed by `python.import-packages` for `python-2026-03` repositories.

`zookeep inspect` inspects the current project ecology and writes `zookeeper-report.json` to the project root.

## Configuration

```
zookeep set registry.path F:/lion/registry.json
```

Set the path to your `registry.json` file so zookeep can check external ecology resources.

## Installation

```
pip install -e .
```
