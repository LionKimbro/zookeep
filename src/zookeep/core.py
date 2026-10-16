"""Worker-owned semantic state and deterministic event reduction.

The runtime installs initial state once. Only the worker mutates g afterwards.
Effects carry outside work; snapshots cross queues as independent copies.
"""

from copy import deepcopy

from zookeep import project


g = {
    "window-id": "spec", "phase": "loading", "fields": {},
    "description": "", "supported": False, "python": False,
    "status": "Loading project…", "status-kind": "info", "setup-after-save": False,
}


def initialize_core_state():
    g.update({
        "window-id": "spec", "phase": "loading", "fields": {},
        "description": "", "supported": False, "python": False,
        "status": "Loading project…", "status-kind": "info", "setup-after-save": False,
    })


def update_project_type_description():
    repo_type = g["fields"].get("repo-type", "").strip()
    g["supported"] = repo_type in project.PROJECT_TYPES
    g["python"] = repo_type == "python-2026-03"
    g["description"] = project.PROJECT_TYPES.get(
        repo_type, "Unsupported presently. You can save this type to JSON, but setup is unavailable."
    )


def reduce_event(event):
    """Advance worker-owned state and return explicit effects; perform no I/O."""
    kind = event["type"]
    if kind == "PROJECT_LOADED":
        g["fields"] = project.get_spec_form_values(event["zoo"])
        g.update(phase="editing", status="Ready.")
        update_project_type_description()
    elif kind == "FIELD_CHANGED" and g["phase"] == "editing":
        g["fields"][event["name"]] = event["value"]
        update_project_type_description()
    elif kind in {"SAVE_REQUESTED", "SAVE_AND_SETUP_REQUESTED"} and g["phase"] == "editing":
        g["fields"] = {name: value.strip() for name, value in event["fields"].items()}
        update_project_type_description()
        for spec in project.SPEC_FIELD_SPECS:
            name = spec["name"]
            if name.startswith("python.") or name == "license":
                if not g["python"]:
                    continue
            if spec["required"] and not g["fields"].get(name):
                g.update(status=f"{spec['label']} is required.")
                g["status-kind"] = "error"
                return []
        g["setup-after-save"] = kind == "SAVE_AND_SETUP_REQUESTED"
        if g["setup-after-save"] and not g["supported"]:
            g.update(status="Repository type unsupported presently. Use Save to retain its metadata.")
            g["status-kind"] = "error"
            return []
        g.update(phase="saving", status="Saving zoo-project.json…")
        g["status-kind"] = "info"
        return [{"type": "WRITE_SPEC", "fields": deepcopy(g["fields"])}]
    elif kind == "SPEC_SAVED":
        if g["setup-after-save"]:
            g.update(phase="setting-up", status="Setting up project, PyDeck, and Git…")
            return [{"type": "RUN_SETUP"}]
        g.update(phase="editing", status="Saved zoo-project.json.")
        g["status-kind"] = "success"
    elif kind == "SETUP_REQUESTED" and g["phase"] == "editing":
        g.update(phase="setting-up", status="Setting up project, PyDeck, and Git…")
        return [{"type": "RUN_SETUP"}]
    elif kind == "SETUP_COMPLETED":
        g.update(phase="editing", status="Setup complete. PyDeck initialized; Git repository ready.")
        g["status-kind"] = "success"
    elif kind == "OPERATION_FAILED":
        g.update(phase="editing", status=event["error"])
        g["status-kind"] = "error"
    elif kind == "CLOSE_REQUESTED":
        g.update(phase="closed", status="Closed.")
    return []


def get_snapshot():
    return deepcopy(g)
