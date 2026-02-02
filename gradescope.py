import datetime
import os

from gradescopeapi.classes.connection import GSConnection
from gradescopeapi.classes.account import Account
import icalendar


def sync():
    connection = GSConnection()
    connection.login(os.environ["GRADESCOPE_EMAIL"], os.environ["GRADESCOPE_PASSWORD"])
    semester = os.environ["GRADESCOPE_SEMESTER"]
    year = str(datetime.date.today().year)
    courses = connection.account.get_courses()["student"]
    courses = {course_id: course for course_id, course in courses.items() if course.semester == semester and course.year == year}
    return [item for course_id, course in courses.items() for item in sync_course(connection, course_id, course)]

def sync_course(connection, course_id, course):
    assignments = connection.account.get_assignments(course_id)
    return [make_todo(course_id, course, assignment) for assignment in assignments]

def make_todo(course_id, course, assignment):
    todo = icalendar.cal.Todo()
    todo.uid = f"gradescope-{assignment.assignment_id}"
    todo.end = assignment.due_date
    # NOTE: Gradescope's due date is inclusive (I think), but iCalendar is exclusive; it's probably fine since the error is in the safe direction.
    todo.categories = ["Gradescope", course.name]
    todo['summary'] = assignment.name
    todo['description'] = f"https://www.gradescope.com/courses/{course_id}/assignments/{assignment.assignment_id}"
    todo['status'] = 'COMPLETED' if assignment.submissions_status == "Submitted" else "NEEDS-ACTION"
    return todo

if __name__ == '__main__':
    todos = sync()
    print("VTODOs from Gradescope")
    for todo in todos:
        print(todo)
