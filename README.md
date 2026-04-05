# zookeep

A system for helping software projects come into being as repositories and keeping them healthy over time.

## Usage

```
zookeep init
zookeep doctor
zookeep inspect
```

`zookeep init` opens a tkinter form and creates `zoo-project.json` in the current project root.

`zookeep doctor` checks `zoo-project.json` and repairs a missing `zookeep-project-guid`, ensuring it is the first key in the file.

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
