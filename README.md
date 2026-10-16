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

`zookeep spec` opens a black and electric-blue tkinter form that creates or edits `zoo-project.json` in the current project root. Existing values are prefilled. Pick a repository type or type your own into the editable combo box. Blue text describes supported types; custom types show a red “unsupported presently” message and can still be saved. Python fields appear only for `python-2026-03`, with separate distribution (`pip install`) and import-package names. **Save** writes metadata only; **Save & setup** also sets up the project.

`zookeep doctor` checks `zoo-project.json`, repairs a missing `zookeep-project-guid`, and migrates legacy `python-package.name` data into explicit `python.distribution` and `python.import-packages` metadata.

`zookeep doctor-pyproject` creates a minimal setuptools/src-layout `pyproject.toml` when it is absent. When it already exists, the command preserves its content and changes only `[project].name` when needed to match `python.distribution.name` in `zoo-project.json`.

`zookeep setup` reads the saved `zoo-project.json` and sets up one of these types:

| Type | Setup |
| --- | --- |
| `basic-2026` | `db/`, project metadata, `.gitignore`, PyDeck initialization, and a local Git repository with an initial commit. No Python scaffolding, `docs/raw/`, README, or license file is generated. |
| `python-2026-03` | The basic foundation plus `docs/raw/`, configured import-package directories with `__init__.py`, minimal or reconciled `pyproject.toml`, README, and license file when supported. |

`db/` holds persistent development and configuration state, including information generated while constructing the project. It is not blanket-ignored in Git.

Both types run **`pydeck26 init`** from the project root. PyDeck owns its seed files in `db/pydeck26/` and also creates `docs/whiteboard/`, including for Basic projects. Git and the `pydeck26` executable must be on PATH. A missing prerequisite or failed PyDeck initialization stops setup before an initial commit; fix the reported issue and rerun. Custom types are saved as metadata, but setup performs no work for them.

Setup preserves existing files and creates an initial Git commit only when the project has no commits. Existing repository indexes and history are preserved on reruns. A project inside a parent repository gets its own repository. Git author identity must already be configured. Empty Python `docs/raw/` directories get a `.gitkeep` so they survive cloning. Local `.zookeep/` and `.pydeck26/` tool state is excluded from the initial commit.

`zookeep init-git` remains available to ensure a project-local Git repository and make its first commit, without generating README or license files. `zookeep publish-github` remains a separate, explicit publication step.

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

## Agent use

Agents may write `zoo-project.json` directly. For a new Basic project:

```json
{
  "name": "notes",
  "repo-type": "basic-2026",
  "repository": {"name": "notes", "visibility": "private"}
}
```

Then run `zookeep doctor` to add its stable GUID and `zookeep setup` to create its working habitat. Run these commands from the target project root (or use the framework's `--execroot` option). Preserve the GUID and unfamiliar metadata when editing existing projects. For Python projects, also supply `python.distribution.name` and a nonempty `python.import-packages` array of `{ "name": "package_name", "path": "src/package_name" }` records. An optional `license` value controls Python license-file generation (`CC0-1.0` or `MIT`).

## Development

Run `python -m unittest discover -s tests -v` (includes a fresh-process real-Tk test; requires a desktop with Tk). See [architecture](docs/code/architecture.md) for state ownership and queue flow. In the editor, Ctrl+Shift+Alt+D enables a Debug menu with a copyable runtime snapshot.
