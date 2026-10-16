# Zookeep architecture

Zookeep keeps LionsCLIApp for configuration and contextual help. `__main__.py` declares commands and adapts them to the project machinery. `project.py` contains metadata transforms, inspection, templates, and file helpers; it owns no GUI state. The existing historical specifications remain in `docs/raw/`; this document describes current implementation.

The editor has exactly two application threads: the main Tk thread and one core worker. The CLI setup command uses the same worker and effects without opening Tk. The other short CLI commands remain synchronous.

```text
Tk callbacks → inbox queue → worker: core.reduce_event → explicit effects
     ↑                         ↓                         ↓
Tk projection ← outbox queue ← detached snapshots ← file/subprocess results
```

`runtime.py` installs queues before starting the worker. The worker owns `core.g`, its bound document register, and the setup machine. Semantic events update core state; explicit `WRITE_SPEC` and `RUN_SETUP` effects perform I/O outside the reducer and feed completion or failure events back into it. Every snapshot is independent of live core state. Recent events and effects are bounded and included for debugging.

`tk.py` owns the hidden Tk root, singleton `spec` Toplevel, window registry, widgets, and detached display snapshots. A 50 ms heartbeat drains the outbox and projects state. Only this thread creates, reads, or changes Tk objects. Field callbacks post semantic events; save requests include a complete field packet so the saved values match the form at click time. Closing queues `CLOSE_REQUESTED`, waits for pending work, then exits after the worker stops. Subprocess effects have 60-second timeouts.

`setup.py` binds the current project in `g` and validated packages in a worker-only register. Its stages validate prerequisites and paths, create type-specific files, run `pydeck26 init`, then ensure Git and its first commit. These registers never communicate across threads and are cleared after each operation. Failures preserve completed files for inspection and retry; setup does not claim to roll back. There is no initial commit after a failed PyDeck operation. Existing Git histories and indexes are not changed by automatic setup. Linked Git worktrees count as existing repositories; a parent repository does not count as the project's own repository.

`basic-2026` is the minimal non-Python type: `db/`, root metadata, Git support, and standard PyDeck initialization. PyDeck adds its own `docs/whiteboard/`; Basic does not add `docs/raw/`, README, license, or Python scaffolding. `python-2026-03` adds raw docs, package paths, packaging metadata, README, and license. Unknown type strings are retained in metadata, with setup unavailable. Project types are declared in `project.PROJECT_TYPES`; GUI descriptions and setup support use the same table.

Agents author the same JSON as humans. There is no parallel agent-only schema or authoring command. `doctor` fills a missing GUID; `setup` can also add one when writing metadata. Existing unknown metadata is preserved, including Python metadata when switching to a non-Python type. The editor hides inactive Python fields without deleting their metadata or source files.
