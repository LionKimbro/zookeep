# zookeep

A system for helping software projects come into being as repositories and keeping them healthy over time.

## Usage

```
zookeep init
zookeep doctor
zookeep setup
zookeep inspect
```

`zookeep init` opens a tkinter form and creates `zoo-project.json` in the current project root, including the Python package name.

`zookeep doctor` checks `zoo-project.json`, repairs a missing `zookeep-project-guid`, and for `python-2026-03` repos adds a `python-package.name: null` placeholder if that field is missing.

`zookeep setup` creates `docs/`, `docs/raw/`, and for `python-2026-03` repos creates `src/<python-package-name>/` when the package name is known.

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
