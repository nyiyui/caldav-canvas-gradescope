import datetime
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import icalendar
import requests


_LINK_NEXT_RE = re.compile(r'<([^>]+)>;\s*rel="next"')


def _read_cookie_header() -> Optional[str]:
    return os.environ["CANVAS_COOKIE_HEADER"].strip()


def _parse_iso_datetime(s: str) -> Optional[datetime.datetime]:
    if not s:
        return None
    try:
        # Canvas typically returns ISO 8601 with Z.
        s2 = s.replace("Z", "+00:00")
        return datetime.datetime.fromisoformat(s2)
    except Exception:
        return None


def _plannable_title(plannable: Dict) -> str:
    for k in ("title", "name"):
        v = plannable.get(k)
        if v:
            return str(v)
    return "(untitled)"


def _plannable_due_at(item: Dict) -> Optional[datetime.datetime]:
    # Common fields across plannable types.
    for path in (
        ("plannable", "due_at"),
        ("plannable", "todo_date"),
        ("plannable", "user_due_date"),
        ("plannable", "lock_at"),
        ("plannable_date",),
    ):
        cur = item
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if not ok:
            continue
        if isinstance(cur, str):
            dt = _parse_iso_datetime(cur)
            if dt is not None:
                return dt
    return None


def _absolute_url(base_url: str, url: str) -> str:
    if not url:
        return base_url
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return base_url.rstrip("/") + "/" + url.lstrip("/")


def _iter_planner_items(
    base_url: str,
    cookie_header: str,
    start_date: datetime.date,
    end_date: datetime.date,
    *,
    planner_filter: Optional[str] = None,
) -> Iterable[Dict]:
    url = base_url.rstrip("/") + "/api/v1/planner/items"
    params = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "per_page": "100",
    }
    if planner_filter:
        params["filter"] = planner_filter

    headers = {
        "Cookie": cookie_header,
        "Accept": "application/json",
        "User-Agent": "caldav-canvas-gradescope/0.1",
    }

    with requests.Session() as s:
        while True:
            resp = s.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                raise RuntimeError(f"Unexpected response shape from {resp.url}: {type(items)}")
            for it in items:
                if isinstance(it, dict):
                    yield it

            link = resp.headers.get("Link", "")
            m = _LINK_NEXT_RE.search(link)
            if not m:
                break
            url = m.group(1)
            params = None  # next link already encodes pagination


def sync() -> List[icalendar.cal.Todo]:
    """Fetch Canvas planner items in the next ~6 months and convert them to VTODOs.

    Environment variables:
    - CANVAS_BASE_URL (required): e.g. https://gatech.instructure.com
    - CANVAS_COOKIE_HEADER (optional): full Cookie header value; if unset, reads cookie-header-content.txt
    """
    base_url = os.environ["CANVAS_BASE_URL"].rstrip("/")
    cookie_header = _read_cookie_header()
    if not cookie_header:
        raise RuntimeError("Missing Canvas cookie header; set CANVAS_COOKIE_HEADER or provide cookie-header-content.txt")

    start_date = datetime.date.today()
    end_date = start_date + datetime.timedelta(days=183)

    todos: List[icalendar.cal.Todo] = []
    for planner_filter in ("incomplete_items", "complete_items"):
        for item in _iter_planner_items(
            base_url,
            cookie_header,
            start_date,
            end_date,
            planner_filter=planner_filter,
        ):
            plannable = item.get("plannable") or {}
            due = _plannable_due_at(item)
            if due is None:
                continue

            plannable_type = str(item.get("plannable_type") or "plannable")
            plannable_id = str(item.get("plannable_id") or plannable.get("id") or "unknown")
            course_id = item.get("course_id")

            todo = icalendar.cal.Todo()
            todo.uid = f"canvas-{plannable_type}-{plannable_id}"
            todo.end = due
            todo.categories = ["Canvas"] + ([f"course-{course_id}"] if course_id else [])
            todo["summary"] = _plannable_title(plannable)

            html_url = item.get("html_url") or plannable.get("html_url") or ""
            todo["description"] = _absolute_url(base_url, str(html_url))

            marked_complete = bool((item.get("planner_override") or {}).get("marked_complete"))
            is_complete = marked_complete or (planner_filter == "complete_items")
            todo["status"] = "COMPLETED" if is_complete else "NEEDS-ACTION"
            todos.append(todo)

    return todos


if __name__ == "__main__":
    for todo in sync():
        print(todo)
