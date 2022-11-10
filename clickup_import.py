import json
import os
from datetime import datetime
from pprint import pprint

from clickup import ClickUp


def import_ac_labels(clickup: ClickUp, path: str = "data/labels.json") -> dict:
    print("Importing AC labels")

    with open(path, "r") as f:
        ac_labels = json.load(f)

    spaces = {}

    for label in ac_labels:
        space = clickup.get_or_create_space(label["name"])
        print(f"- {space['name']}")

        spaces[label["id"]] = space

    return spaces


def get_members(clickup: ClickUp, path: str = "data/users.json") -> dict:
    print("Get members")

    with open(path, "r") as f:
        ac_users = json.load(f)

    members = {}

    for user in ac_users:
        if member := clickup.get_member(user["email"]):
            members[user["id"]] = member

    return members


def import_ac_projects(
    clickup: ClickUp, spaces: dict, members: dict, path: str = "data"
) -> dict:
    print("Importing AC projects")

    with open(os.path.join(path, "projects.json"), "r") as f:
        ac_projects = json.load(f)

    folders = {}
    docs = {}
    pages = {}
    statuses = {}
    tasks = {}

    for project in ac_projects:
        project_path = os.path.join(path, "projects", str(project["id"]))

        space = spaces[project["label_id"]]["id"]

        folder = clickup.get_or_create_folder(space, project["name"])
        folders[project["id"]] = folder
        print(f"- {folder['name']}")

        doc = clickup.get_or_create_doc(folder["id"], "Documents")
        page = import_ac_note(clickup, doc["id"], "About", project["body"])
        docs[project["id"]] = doc

        task_list = clickup.get_or_create_list(folder["id"], "Tasks")

        # Import notes/documents!
        # Important fields are: name, body_plain_text, created_by_id, created_by_name
        with open(os.path.join(project_path, "notes.json")) as f:
            project_notes = json.load(f)

        for note in project_notes:
            body = f"Originally created by {note['created_by_name']}"
            body = f"{body} on {getDate(note['created_on'])}"
            body = f"{body}\n\n---\n\n{note['body_plain_text']}"

            page = import_ac_note(clickup, doc["id"], note["name"], body)
            pages[note["id"]] = page

        # import tasks
        with open(os.path.join(project_path, "tasks.json")) as f:
            project_tasks = json.load(f)

        task_lists = {tl["id"]: tl for tl in project_tasks["task_lists"]}
        # pprint(task_lists)

        for pt in project_tasks["tasks"]:
            task_path = os.path.join(project_path, "tasks", str(pt["id"]))
            with open(os.path.join(task_path, "tasks.json"), "r") as f:
                ac_task = json.load(f)["single"]

            tasks[ac_task["id"]] = import_ac_task(
                clickup, task_list["id"], ac_task, task_lists, members
            )


def getDate(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d, %H:%M:%S")


def import_ac_note(clickup: ClickUp, doc: str, name: str, body: str) -> dict:
    return clickup.get_or_create_page(doc, name, body)


def import_ac_task(
    clickup: ClickUp, task_list_id: int, ac_task: dict, task_lists: dict, members: dict
) -> dict:
    status = getTaskStatus(ac_task["task_list_id"], task_lists)

    details = dict(
        description=ac_task["body"],
        assignees=[],
        tags=[],
        status=status,
        priority=1 if ac_task["is_important"] else 3,
        due_date_time=False,
        time_estimate=ac_task["estimate"] * 60 * 60,
        start_date_time=False,
    )

    if assignee := members.get(ac_task["assignee_id"]):
        details["assignees"] = [assignee]

    if due_date := ac_task["due_on"]:
        details["due_date"] = due_date * 1000

    if start_date := ac_task["start_on"]:
        details["start_date"] = start_date * 1000

    return clickup.get_or_create_task(
        task_list_id, ac_task["name"], json.dumps(details)
    )


def getTaskStatus(list_id: int, task_lists: dict) -> str:
    name = task_lists[list_id]["name"].lower()

    if name == "inbox" or name == "to do":
        return "Open"

    if name == "in progress":
        return "In progress"

    if name == "done":
        return "Closed"

    if name == "project size":
        return "Open"


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    clickup = ClickUp(
        secrets["team_id"], secrets["api_token_v1"], secrets["api_token_v2"]
    )

    spaces = import_ac_labels(clickup)
    print()

    members = get_members(clickup)
    print()

    projects = import_ac_projects(clickup, spaces, members)
    print()
