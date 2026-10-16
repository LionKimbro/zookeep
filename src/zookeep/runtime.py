"""One core worker, two queues, explicit effects, and bounded subprocess work.

Main thread owns lifecycle and consumes outbox. Worker owns core and project data.
Queues are installed before starting the worker, discarded after it has stopped.
"""

from collections import deque
from copy import deepcopy
from pathlib import Path
from queue import Queue
from threading import Thread

from zookeep import core, project, setup


g = {"thread": None, "root": None}
queues = {"inbox": None, "outbox": None}
reg = {"zoo": None}  # Worker-only bound document, never read by Tk.
recent_events = deque(maxlen=30)
recent_effects = deque(maxlen=30)


def start_runtime(root):
    if g["thread"] is not None and g["thread"].is_alive():
        raise RuntimeError("Zookeep core worker is already running.")
    g["root"] = Path(root).resolve()
    queues.update(inbox=Queue(), outbox=Queue())
    recent_events.clear()
    recent_effects.clear()
    core.initialize_core_state()
    g["thread"] = Thread(target=handle_worker_event_loop_until_closed, name="zookeep-core")
    g["thread"].start()


def post_event(event):
    queues["inbox"].put(deepcopy(event))


def publish_snapshot():
    queues["outbox"].put({
        "state": core.get_snapshot(),
        "events": list(recent_events), "effects": list(recent_effects),
    })


def dispatch_event(event):
    recent_events.append(deepcopy(event))
    effects = core.reduce_event(event)
    publish_snapshot()
    for effect in effects:
        recent_effects.append(deepcopy(effect))
        route_effect(effect)


def route_effect(effect):
    try:
        if effect["type"] == "WRITE_SPEC":
            # Re-read so an extension added since opening the form is preserved.
            reg["zoo"] = project.read_zoo_project(g["root"])
            zoo = project.make_spec_zoo_project(effect["fields"], reg["zoo"])
            project.write_zoo_project(g["root"], zoo)
            dispatch_event({"type": "SPEC_SAVED"})
        elif effect["type"] == "RUN_SETUP":
            setup.run_setup(g["root"])
            dispatch_event({"type": "SETUP_COMPLETED"})
    except Exception as exc:
        dispatch_event({"type": "OPERATION_FAILED", "error": str(exc)})


def handle_worker_event_loop_until_closed():
    try:
        reg["zoo"] = project.read_zoo_project(g["root"])
        dispatch_event({"type": "PROJECT_LOADED", "zoo": reg["zoo"]})
    except Exception as exc:
        dispatch_event({"type": "OPERATION_FAILED", "error": str(exc)})
    try:
        while core.g["phase"] != "closed":
            event = queues["inbox"].get()
            try:
                dispatch_event(event)
            except Exception as exc:
                dispatch_event({"type": "OPERATION_FAILED", "error": str(exc)})
    finally:
        reg["zoo"] = None


def run_setup_command(root):
    """CLI uses the same worker/effects as Tk; errors yield a nonzero exit."""
    start_runtime(root)
    try:
        loaded = queues["outbox"].get()
        if loaded["state"]["status-kind"] == "error":
            raise ValueError(loaded["state"]["status"])
        post_event({"type": "SETUP_REQUESTED"})
        while True:
            snapshot = queues["outbox"].get()["state"]
            if snapshot["phase"] == "editing":
                if snapshot["status-kind"] == "error":
                    raise ValueError(snapshot["status"])
                print(snapshot["status"])
                return
    finally:
        post_event({"type": "CLOSE_REQUESTED"})
        g["thread"].join()
