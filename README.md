Canvas/Gradescope → CalDAV Tasks Sync

`gradescope.py` and `canvas.py` return a list of [icalendar.cal.Todo](https://icalendar.readthedocs.io/en/stable/api.html#icalendar.cal.Todo) objects,
which is then synced with your CalDAV server by `caldav_sync.py`.

Canvas sync uses the Planner API endpoint `/api/v1/planner/items` to fetch items from today through ~6 months.
It authenticates using a raw Cookie header from `CANVAS_COOKIE_HEADER` (fallback: `cookie-header-content.txt`).
Also set `CANVAS_BASE_URL` (e.g. `https://gatech.instructure.com`).

Note for Gradescope: even if you're using SSO, you can still set a password by going through their password reset process.

Why use API?
- auto-complete tasks on CalDAV when done on Canvas
- idk

Status:
- Since this year (Dec 2025 to be exact), GT made API access 認可性…aren't we a Tech school???
- requested access (2026-Jan-18, so expect response by EOD 2026-Jan-21)
