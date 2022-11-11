import json
import os
from datetime import datetime
from glob import glob
from pprint import pprint

from clickup import ClickUp
from markdownify import markdownify


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


def import_ac_attachments(
    click_up: ClickUp, spaces: dict, tasks: dict, path: str = "data"
) -> None:
    print("Importing AC Attachments")
    projects_json = glob((os.path.join(path, "attachments", "*.json")))
    for project_json in projects_json:
        with open(project_json) as f:
            attachments = json.load(f)

            # Filter out google docs
            attachments = [
                a for a in attachments if a["class"] != "GoogleDriveAttachment"
            ]

            for attachment in attachments:

                a_id = attachment["id"]
                a_name = attachment["name"]

                if "parent_type" in attachment:
                    if (
                        attachment["parent_type"] == "Task"
                        and tasks[attachment["parent_id"]] is not None
                    ):
                        # Attach to task
                        task = tasks[attachment["parent_id"]]["id"]
                        file_path = os.path.join(
                            os.path.splitext(os.path.abspath(project_json))[0],
                            f"{a_id}__{a_name}",
                        )

                        pprint(
                            click_up.upload_attachment_to_task(task, a_name, file_path)
                        )
                    elif attachment["parent_type"] == "Comment":
                        # Was attached to comment, attach to task
                        pass

                    elif attachment["parent_type"] == "Note":
                        # Was attached to a note, attach to document
                        pass
                    else:
                        # It was... somewhere?! Attach to default document. Probably a task that was not imported.
                        pass
                else:
                    # Was attached to project, attach to default document.
                    pass


def import_ac_projects(
    clickup: ClickUp, spaces: dict, members: dict, path: str = "data"
) -> dict:
    print("Importing AC projects")

    with open(os.path.join(path, "projects.json"), "r") as f:
        ac_projects = json.load(f)

    folders = {}
    docs = {}
    pages = {}
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
            body = f"{body} on {get_date(note['created_on'])}"
            body = f"{body}\n\n---\n\n{note['body_plain_text']}"

            page = import_ac_note(clickup, doc["id"], note["name"], body)
            pages[note["id"]] = page

        # import tasks
        with open(os.path.join(project_path, "tasks.json")) as f:
            project_tasks = json.load(f)

        for pt in project_tasks["tasks"]:
            task_path = os.path.join(project_path, "tasks", str(pt["id"]))
            with open(os.path.join(task_path, "tasks.json"), "r") as f:
                ac_task = json.load(f)

            tasks[ac_task["single"]["id"]] = import_ac_task(
                clickup, task_list["id"], ac_task, members
            )

        # import time records
        with open(os.path.join(project_path, "time-records.json")) as f:
            records = json.load(f)["time_records"]

        for record in records:
            parent_id = record["parent_id"]
            if parent_id == project["id"]:
                parent = folder
            else:
                parent = tasks[parent_id]

    return folders, docs, pages, tasks


def get_date(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d, %H:%M:%S")


def import_ac_note(clickup: ClickUp, doc: str, name: str, body: str) -> dict:
    return clickup.get_or_create_page(doc, name, body)


def import_ac_task(
    clickup: ClickUp, task_list_id: int, ac_task: dict, members: dict
) -> dict:
    if not is_task_importable(ac_task):
        return None

    single = ac_task["single"]
    status = get_task_status(ac_task)

    data = dict(
        description=html_to_markdown(single["body"]),
        assignees=[],
        tags=[],
        status=status,
        priority=1 if single["is_important"] else None,
        due_date_time=False,
        time_estimate=single["estimate"],
        start_date_time=False,
    )

    if member := members.get(single["assignee_id"]):
        data["assignees"] = [member["user"]["id"]]

    if due_date := single["due_on"]:
        data["due_date"] = due_date * 1000

    if start_date := single["start_on"]:
        data["start_date"] = start_date * 1000

    task = clickup.get_or_create_task(task_list_id, single["name"], json.dumps(data))

    data = dict()

    if member := members.get(single["created_by_id"]):
        data["creator"] = dict(id=member["user"]["id"])

    if subscribers := ac_task["subscribers"]:
        data["followers"] = dict(
            add=[
                members[sub]["user"]["id"] if members[sub] else None
                for sub in subscribers
            ]
        )

    task = clickup.update_task(task["id"], data)

    for subtask in ac_task["subtasks"]:
        data = dict(
            parent=task["id"],
            name=subtask["name"],
            status="Closed" if subtask["is_completed"] else status,
        )

        if member := members.get(subtask["assignee_id"]):
            data["assignees"] = [member["user"]["id"]]

        clickup.get_or_create_task(task_list_id, subtask["name"], json.dumps(data))

    for comment in ac_task["comments"]:
        clickup.get_or_create_comment(task["id"], comment["body_plain_text"])

    return task


def is_task_importable(ac_task: dict) -> bool:
    if ac_task["tracked_time"] > 0:
        return True

    if ac_task["tracked_expenses"] > 0:
        return True

    if ac_task["single"]["comments_count"] > 0:
        return True

    if get_task_status(ac_task) != "Open":
        return True

    return False


def get_task_status(ac_task: dict) -> str:
    if ac_task["single"]["is_completed"]:
        return "Closed"

    name = ac_task["task_list"]["name"].lower()

    if name == "inbox" or name == "to do":
        return "Open"

    if name == "in progress":
        return "In progress"

    if name == "done":
        return "Closed"

    if name == "project size":
        return "Open"


def html_to_markdown(html: str) -> str:
    return markdownify(html, heading_style="ATX")


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

    folders, docs, pages, tasks = import_ac_projects(clickup, spaces, members)
    print()

    attachments = import_ac_attachments(clickup, spaces, tasks)
    print()
