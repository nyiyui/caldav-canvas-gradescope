# Sync Canvas and Gradescope Tasks to CalDAV

Screenshot of [Planify](https://useplanify.com/) with synced tasks:

<img width="812" height="417" alt="screenshot of TODO app with 3/5 tasks synced from Canvas and Gradescope" src="https://github.com/user-attachments/assets/d33440e8-d5da-49b5-96a5-f6c495a441a4" />

This script syncs [Canvas](https://www.instructure.com/canvas) ([planner items](https://developerdocs.instructure.com/services/canvas/resources/planner)) and [Gradescope](https://www.gradescope.com/) (assignments) to a CalDAV server of your choosing.
(I use it to sync my assignments to my CalDAV server.)
You can then view your tasks on many apps, from Planify on Linux to [jtx Board](https://jtx.techbee.at/) (with [DAVx5](https://www.davx5.com/)) on Android.

## Setup

### CalDAV

To sync your tasks to a CalDAV server, you need:
- `CALDAV_URL`: The URL of the CalDAV server itself such as `https://cdav.migadu.com`
- `CALDAV_USERNAME` and `CALDAV_PASSWORD` for authenticating to the server itself (OAuth2 and other methods are not supported, but feel free to submit a PR)
- `CALDAV_CALENDAR_NAME`: The calendar where you want to have tasks placed

### Gradescope

(If you are using SSO to login, then you need to set a password for your account by ["resetting" your password](https://www.gradescope.com/reset_password).)
To get assignments from Gradescope, you need:
- `GRADESCOPE_EMAIL`: The email you use to login; probably is your institutional email address if using SSO.
- `GRADESCOPE_SEMESTER`: Probably `Fall` or `Spring`, but you can figure this out by looking at your home page in Gradescope. ([Ref. to used API](https://github.com/nyuoss/gradescope-api/blob/a0daa54cd5fedc41e37c5cc163f0fd80922b404d/src/gradescopeapi/classes/courses.py#L8))
- `GRADESCOPE_PASSWORD`

### Canvas

To get planner items from Canvas, you need:
- `CANVAS_BASE_URL` which is the URL to your Canvas instance, such as `https://gatech.instructure.com`
- `CANVAS_COOKIE_HEADER` which is the contents of your `Cookie` request header, which you can copy from your browser's inspect tool
  - This tool doesn't use user access tokens since my school doesn't issue them anymore

## Hacking

`gradescope.py` and `canvas.py` return a list of [icalendar.cal.Todo](https://icalendar.readthedocs.io/en/stable/api.html#icalendar.cal.Todo) objects,
which is then synced with your CalDAV server by `caldav_sync.py`.

Canvas sync uses the Planner API endpoint `/api/v1/planner/items` to fetch items from today through ~6 months.
It authenticates using a raw Cookie header from `CANVAS_COOKIE_HEADER` (fallback: `cookie-header-content.txt`).
Also set `CANVAS_BASE_URL` (e.g. `https://gatech.instructure.com`).
