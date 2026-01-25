import gradescope
import caldav_sync

if __name__ == "__main__":
    todos = gradescope.sync()
    for todo in todos:
        print(todo)
    caldav_sync.sync_todos(todos)
