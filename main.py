import datetime

import icalendar

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


def _make_failure_todo(source: str, exc: Exception) -> icalendar.cal.Todo:
    now = datetime.datetime.now().astimezone()
    due = now + datetime.timedelta(hours=24)

    todo = icalendar.cal.Todo()
    todo.uid = f"sync-failure-{source}"
    todo.end = due
    todo.categories = ["SyncFailure", source]
    todo["summary"] = f"Fix {source} sync (failed)"
    todo["description"] = f"{source} sync failed at {now.isoformat()}: {type(exc).__name__}: {exc}"
    todo["status"] = "NEEDS-ACTION"
    return todo


def _to_local_dt(dt: datetime.datetime, local_tz: datetime.tzinfo) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=local_tz)
    return dt.astimezone(local_tz)


def _force_todo_local_timezone(todo: icalendar.cal.Todo, local_tz: datetime.tzinfo) -> None:
    for k in ("DUE", "DTSTART", "DTEND", "COMPLETED"):
        v = todo.get(k)
        if v is None:
            continue
        dt = getattr(v, "dt", v)
        if isinstance(dt, datetime.datetime):
            todo[k] = _to_local_dt(dt, local_tz)


if __name__ == "__main__":
    errors = []
    todo_lists = []

    try:
        todo_lists.append(gradescope.sync())
    except Exception as e:
        errors.append(("gradescope", e))
        todo_lists.append([_make_failure_todo("gradescope", e)])

    try:
        todo_lists.append(canvas.sync())
    except Exception as e:
        errors.append(("canvas", e))
        todo_lists.append([_make_failure_todo("canvas", e)])

    todos = _merge_by_uid(todo_lists)
    local_tz = datetime.datetime.now().astimezone().tzinfo
    if local_tz is not None:
        for todo in todos:
            _force_todo_local_timezone(todo, local_tz)

    for todo in todos:
        print(todo)

    caldav_sync.sync_todos(todos)
