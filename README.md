Canvas → CalDAV Tasks Sync (but use the Canvas API)

`gradescope.py` (and `canvas.py` in the future) return a list of [icalendar.cal.Todo](https://icalendar.readthedocs.io/en/stable/api.html#icalendar.cal.Todo) objects,
which is then synced with your CalDAV server by `caldav_sync.py`.

Note for Gradescope: even if you're using SSO, you can still set a password by going through their password reset process.

Why use API?
- auto-complete tasks on CalDAV when done on Canvas
- idk

Status:
- Since this year (Dec 2025 to be exact), GT made API access 認可性…aren't we a Tech school???
- requested access (2026-Jan-18, so expect response by EOD 2026-Jan-21)
