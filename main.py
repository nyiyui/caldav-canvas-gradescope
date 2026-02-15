import caldav_sync
import canvas
import gradescope


def _merge_by_uid(todo_lists):
    merged = {}
    for todos in todo_lists:
        for t in todos:
            uid = str(t.get("UID")) if t.get("UID") is not None else None
            if uid:
                merged[uid] = t
    return list(merged.values())


if __name__ == "__main__":
    errors = []
    todo_lists = []

    try:
        todo_lists.append(gradescope.sync())
    except Exception as e:
        errors.append(("gradescope", e))

    try:
        todo_lists.append(canvas.sync())
    except Exception as e:
        errors.append(("canvas", e))

    if not todo_lists:
        msgs = ", ".join([f"{src}: {err}" for src, err in errors])
        raise RuntimeError(f"Both sources failed: {msgs}")

    todos = _merge_by_uid(todo_lists)
    for todo in todos:
        print(todo)

    caldav_sync.sync_todos(todos)
