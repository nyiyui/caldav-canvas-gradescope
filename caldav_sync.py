"""
caldav_sync.py

Utility to sync a list of icalendar.cal.Todo objects to a CalDAV server.

Behavior implemented:
- If a task on the server shares the same UID, SUMMARY and DUE with a local Todo,
  then the server STATUS is preserved (no change).
- If a server task with the same UID differs in SUMMARY or DUE, the server task's
  STATUS is set to "NEEDS-ACTION".
- New local Todos (UID not found on server) are created on the calendar.

This module attempts to work with the python-caldav and icalendar libraries.
It includes best-effort fallbacks for different caldav client object shapes, and
raises an informative error if the environment's caldav API is incompatible.

Note: CalDAV server libraries vary; this module documents where adaptation may
be required (create/update methods). It performs network operations when
called; tests and usage should be done in a safe environment.
"""

from typing import List, Tuple, Optional
import logging
import os

from caldav import DAVClient

from icalendar import Calendar
from icalendar.cal import Todo
from datetime import datetime, date

logger = logging.getLogger(__name__)


def _normalize_dt(val) -> Optional[datetime]:
    """Normalize an icalendar DUE value to a datetime for comparison.

    Accepts icalendar vDDDTypes (which behaves like datetime), date, or
    datetime. Returns None if value is None or can't be interpreted.
    """
    if val is None:
        return None
    # icalendar often wraps datetimes in types that behave like datetime
    try:
        if isinstance(val, datetime):
            return val
        if isinstance(val, date):
            # convert date -> datetime at midnight (naive)
            return datetime(val.year, val.month, val.day)
        # some wrappers expose .dt
        if hasattr(val, 'dt'):
            dt = getattr(val, 'dt')
            if isinstance(dt, (datetime, date)):
                if isinstance(dt, date) and not isinstance(dt, datetime):
                    return datetime(dt.year, dt.month, dt.day)
                return dt
    except Exception:
        pass
    return None


def _extract_vtodo_and_calendar(server_todo_obj) -> Tuple[object, Calendar]:
    """Try to extract the icalendar.Calendar and its VTODO component from a server-side object.

    Returns a tuple (vtodo_component, calendar_obj). The vtodo_component is an
    icalendar component (mapping-like) and calendar_obj is an icalendar.Calendar
    instance.

    This function tries several common attribute names used by python-caldav
    wrappers: vobject_instance, instance, data, _get_data(), etc.
    """
    # Prefer object-provided parsed instance
    parsed_cal = None
    if hasattr(server_todo_obj, 'vobject_instance') and getattr(server_todo_obj, 'vobject_instance') is not None:
        parsed_cal = server_todo_obj.vobject_instance
    elif hasattr(server_todo_obj, 'instance') and getattr(server_todo_obj, 'instance') is not None:
        parsed_cal = server_todo_obj.instance
    else:
        # Try common raw-data attributes/methods
        raw = None
        for attr in ('data', '_data', 'raw', 'ical', '_get_data'):
            if hasattr(server_todo_obj, attr):
                val = getattr(server_todo_obj, attr)
                try:
                    raw = val() if callable(val) else val
                except Exception:
                    continue
                if raw:
                    break
        if raw is not None:
            parsed_cal = Calendar.from_ical(raw if isinstance(raw, (bytes, str)) else raw.encode() if isinstance(raw, str) else raw)

    if parsed_cal is None:
        raise RuntimeError("Unable to extract iCalendar data from server todo object; adjust this module for your caldav client API")

    # parsed_cal may already be a Calendar or a vobject. Ensure it's a Calendar
    if not isinstance(parsed_cal, Calendar):
        try:
            parsed_cal = Calendar.from_ical(parsed_cal.to_ical())
        except Exception:
            # last resort: assume parsed_cal is string-like
            parsed_cal = Calendar.from_ical(parsed_cal)

    for comp in parsed_cal.walk():
        if comp.name == 'VTODO':
            return comp, parsed_cal
    raise RuntimeError('No VTODO component found inside server calendar data')


def sync_todos(todos: List[Todo]):
    """Synchronize a list of icalendar.cal.Todo objects to a CalDAV calendar.

    Credentials are read from environment variables:
    - CALDAV_URL
    - CALDAV_USERNAME
    - CALDAV_PASSWORD

    The target calendar display name can be provided via CALDAV_CALENDAR_NAME; if
    unset, the first calendar returned by the server is used.

    Arguments:
    - todos: list of icalendar.cal.Todo objects (as produced by gradescope.py)

    Returns: a list of dicts describing actions taken for each todo.

    Important behavior implemented to follow your spec:
    - When server has a todo with same UID, SUMMARY and DUE, the server's STATUS is preserved.
    - When server has same UID but different SUMMARY or DUE, set server STATUS to 'NEEDS-ACTION'.
    - If UID not found on server, create the todo on the server calendar.

    Notes: This function tries to call common caldav methods and contains
    informative errors when a particular caldav client object doesn't implement
    expected helpers (e.g. add_todo, save/put methods). Adaptation might be
    required for your environment.
    """
    # Read credentials from environment; KeyError will fail early if missing.
    caldav_url = os.environ["CALDAV_URL"]
    username = os.environ["CALDAV_USERNAME"]
    password = os.environ["CALDAV_PASSWORD"]

    # Calendar name is read exclusively from the environment
    calendar_name = os.environ.get("CALDAV_CALENDAR_NAME")

    client = DAVClient(url=caldav_url, username=username, password=password)
    principal = client.principal()
    calendars = principal.calendars()
    if not calendars:
        raise RuntimeError('No calendars found for the provided account')

    calendar = None
    if calendar_name:
        for c in calendars:
            try:
                props = getattr(c, 'get_properties', None)
                if props:
                    # many caldav libs allow prop retrieval; tolerate failure
                    displayname = c.get_properties(["{DAV:}displayname"]) if callable(c.get_properties) else None
                else:
                    displayname = getattr(c, 'name', None)
            except Exception:
                displayname = getattr(c, 'name', None)
            name = None
            if isinstance(displayname, dict):
                # prop lookup shape: {"{DAV:}displayname": 'Calendar name'}
                name = next(iter(displayname.values()), None)
            else:
                name = displayname
            if name and name == calendar_name:
                calendar = c
                break
    if calendar is None:
        calendar = calendars[0]

    # get server todos
    try:
        server_todos = calendar.todos() if hasattr(calendar, 'todos') else []
    except Exception:
        # some clients expose .objects() or .items(); try to be permissive
        try:
            server_todos = calendar.events() if hasattr(calendar, 'events') else []
        except Exception:
            server_todos = []

    # build map uid -> (server_todo_obj, server_vtodo_component, server_calendar)
    server_map = {}
    for s in server_todos:
        try:
            server_vtodo, server_calendar = _extract_vtodo_and_calendar(s)
            uid = str(server_vtodo.get('UID')) if server_vtodo.get('UID') is not None else None
            if uid:
                server_map[uid] = (s, server_vtodo, server_calendar)
        except Exception:
            logger.debug('Skipping server todo we could not parse', exc_info=True)
            continue

    actions = []

    for local in todos:
        local_uid = str(local.get('UID')) if local.get('UID') is not None else None
        local_summary = str(local.get('SUMMARY')) if local.get('SUMMARY') is not None else ''
        local_due = _normalize_dt(local.get('DUE'))

        if local_uid is None:
            actions.append({'uid': None, 'action': 'skipped', 'reason': 'local todo missing UID'})
            continue

        server_entry = server_map.get(local_uid)
        if server_entry is None:
            # create on server
            ical_bytes = local.to_ical()
            created = False
            try:
                if hasattr(calendar, 'add_todo'):
                    calendar.add_todo(ical_bytes)
                    created = True
                elif hasattr(calendar, 'add_event'):
                    calendar.add_event(ical_bytes)  # sometimes both work
                    created = True
                else:
                    # try generic create
                    if hasattr(calendar, 'save'):
                        calendar.save(ical_bytes)
                        created = True
            except Exception as e:
                logger.exception('Failed to create todo on server')
                actions.append({'uid': local_uid, 'action': 'create_failed', 'error': str(e)})
                continue

            actions.append({'uid': local_uid, 'action': 'created' if created else 'create_attempted'})
            continue

        # server-side todo exists
        server_obj, server_vtodo, server_cal = server_entry
        server_summary = str(server_vtodo.get('SUMMARY')) if server_vtodo.get('SUMMARY') is not None else ''
        server_due = _normalize_dt(server_vtodo.get('DUE'))

        # Compare summary and due (normalize datetimes)
        same_summary = server_summary == local_summary
        same_due = (server_due == local_due) or (server_due is None and local_due is None)

        if same_summary and same_due:
            # preserve server status (no changes)
            actions.append({'uid': local_uid, 'action': 'preserved_server_status', 'server_status': str(server_vtodo.get('STATUS'))})
            continue

        # summary or due differ: set server status to NEEDS-ACTION
        try:
            server_vtodo['STATUS'] = 'NEEDS-ACTION'
            # write back full calendar
            updated_ical = server_cal.to_ical()
            updated = False
            # Try common save/update methods on server_obj
            if hasattr(server_obj, 'save'):
                try:
                    server_obj.save(updated_ical)
                    updated = True
                except TypeError:
                    # some implementations want bytes
                    server_obj.save(updated_ical)
                    updated = True
            elif hasattr(server_obj, 'put'):
                server_obj.put(updated_ical)
                updated = True
            elif hasattr(server_obj, '_put'):
                server_obj._put(updated_ical)
                updated = True
            else:
                # fallback: try calendar.put with the object's url (if present)
                obj_url = getattr(server_obj, 'url', None)
                if obj_url and hasattr(calendar, 'client'):
                    # raw PUT using caldav client session
                    try:
                        calendar.client.put(obj_url, updated_ical)
                        updated = True
                    except Exception:
                        pass

            actions.append({'uid': local_uid, 'action': 'set_needs_action' if updated else 'set_needs_action_attempted'})
        except Exception as e:
            logger.exception('Failed to update server todo status')
            actions.append({'uid': local_uid, 'action': 'update_failed', 'error': str(e)})

    return actions


if __name__ == '__main__':
    print('caldav_sync module: import and call sync_todos(...) from your script')
