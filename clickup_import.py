import json
import os
import re
from datetime import datetime
from glob import glob
from pprint import pprint

from markdownify import markdownify

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


def get_members(
    clickup: ClickUp, path: str = "data/users.json", tokens: dict = {}
) -> dict:
    print("Get members")

    with open(path, "r") as f:
        ac_users = json.load(f)

    members = {}

    for user in ac_users:
        id = user["id"]
        if member := clickup.get_member(user["email"]):
            members[id] = member
            members[id]["token"] = tokens.get(user["email"], tokens.get("default"))

    return members


def import_ac_attachments(
    click_up: ClickUp, spaces: dict, tasks: dict, comment_map: dict, folders:dict, path: str = "data"
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
                file_path = os.path.join(
                            os.path.splitext(os.path.abspath(project_json))[0],
                            f"{a_id}__{a_name}",
                        )

                if "parent_type" in attachment:
                    if (
                        attachment["parent_type"] == "Task"
                        and tasks[attachment["parent_id"]] is not None
                    ):
                        # Attach to task
                        task = tasks[attachment["parent_id"]]["id"]
                        click_up.upload_attachment_to_task(task, a_name, file_path)

                    elif attachment["parent_type"] == "Comment":
                        # Was attached to comment, attach to task
                        task = tasks[comment_map[attachment["parent_id"]]]["id"]
                        click_up.upload_attachment_to_task(task, a_name, file_path)

                    elif attachment["parent_type"] == "Note":
                        # Was attached to a note, attach to document
                        pass
                    else:
                        # It was... somewhere?! Attach to default document. Probably a task that was not imported.
                        pass
                else:
                    # Was attached to project, attach to default document.
                    doc = clickup.get_or_create_doc(folders[attachment["project_id"]]["id"], "Documents")
                    page = import_ac_note(clickup, doc["id"], "AC Attachments", "Attachments from ActiveCollab")
                    click_up.upload_attachment_to_document(doc, page, a_name, file_path)

def import_ac_projects(
    clickup: ClickUp, spaces: dict, members: dict, path: str = "data"
) -> tuple:
    print("Importing AC projects")

    with open(os.path.join(path, "projects.json"), "r") as f:
        ac_projects = json.load(f)

    with open(os.path.join(path, "companies.json"), "r") as f:
        companies = json.load(f)

    folders = {}
    docs = {}
    pages = {}
    tasks = {}
    comment_map = {}

    for project in ac_projects:
        project_path = os.path.join(path, "projects", str(project["id"]))

        space = spaces[project["label_id"]]["id"]

        folder = clickup.get_or_create_folder(space, project["name"])
        folders[project["id"]] = folder
        folder_name = folder["name"]
        print(f"- {folder_name}")

        list_name = re.split(r"[\[\(:;]", folder_name)[0].strip()

        doc = clickup.get_or_create_doc(folder["id"], "Documents")
        page = import_ac_note(clickup, doc["id"], "About", project["body"])
        docs[project["id"]] = doc

        task_list = clickup.get_or_create_list(folder["id"], list_name)
        import_project_details(clickup, task_list["id"], project, companies)

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

            tasks[ac_task["single"]["id"]], task_comment_map = import_ac_task(
                clickup, task_list["id"], ac_task, members
            )

            if task_comment_map is not None:
                comment_map = comment_map | task_comment_map

        for pt in project_tasks["completed_task_ids"]:
            task_path = os.path.join(project_path, "tasks/archived", str(pt))
            with open(os.path.join(task_path, "tasks.json"), "r") as f:
                ac_task = json.load(f)

            tasks[ac_task["single"]["id"]], task_comment_map = import_ac_task(
                clickup, task_list["id"], ac_task, members
            )

            if task_comment_map is not None:
                comment_map = comment_map | task_comment_map

        # import time records
        with open(os.path.join(project_path, "time-records.json")) as f:
            records = json.load(f)

        for record in records["time_records"]:
            parent_id = record["parent_id"]
            if parent_id == project["id"]:
                parent = folder
            else:
                parent = tasks[parent_id]

            if not parent:
                break

            data = dict()

    return folders, docs, pages, tasks, comment_map


def import_project_details(
    clickup: ClickUp, task_list_id: int, project: dict, companies: list
) -> dict:
    if companies := list(filter(lambda x: x["id"] == project["company_id"], companies)):
        print("- Import project details")
        organisation = "King's College, London"
        faculty, department = companies[0]["name"].split(":")
        faculty = faculty.strip()
        department = department.strip()

        if faculty == "External":
            organisation = None
        if faculty == "KCL":
            faculty = None
        if faculty == "King's":
            faculty = department
            department = None

        custom_fields = []
        fields = clickup.get_custom_fields(task_list_id)
        faculty_field = list(filter(lambda x: x["name"] == "Faculty", fields))[0]
        faculty_options = list(
            filter(
                lambda x: x["name"] == faculty, faculty_field["type_config"]["options"]
            )
        )

        custom_fields = [
            dict(
                id="4c0f85e5-e82d-4980-b511-de41cefd6163",
                value=list(map(lambda x: x["id"], faculty_options))[0],
            ),
            # dict(id="342f55be-f7b0-4508-8242-2d573696e299", value=[department]),
            # dict(id="d98a262e-632d-4b9f-8776-520fbe5b29ee", value=[organisation]),
        ]
        data = dict(
            description="",
            assignees=[],
            tags=["project details"],
            status="Open",
            priority=None,
            due_date_time=False,
            time_estimate=None,
            start_date_time=False,
            custom_fields=custom_fields,
        )

        pprint(data)
        task = clickup.get_or_create_task(
            task_list_id, "Project details", json.dumps(data)
        )
        pprint(task)

    return {}


def get_date(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d, %H:%M:%S")


def import_ac_note(clickup: ClickUp, doc: str, name: str, body: str) -> dict:
    return clickup.get_or_create_page(doc, name, body)


def import_ac_task(
    clickup: ClickUp, task_list_id: int, ac_task: dict, members: dict
) -> tuple:
    task_comment_map = {}

    if not is_task_importable(ac_task):
        return None, None

    single = ac_task["single"]
    name = single["name"]

    tags = get_task_tags(name)
    status = get_task_status(ac_task)

    data = dict(
        description=html_to_markdown(single["body"]),
        assignees=[],
        tags=tags,
        status=status,
        priority=1 if single["is_important"] else None,
        due_date_time=False,
        time_estimate=single["estimate"] * 60 * 60 * 1000,
        start_date_time=False,
    )

    if member := members.get(single["assignee_id"]):
        data["assignees"] = [member["user"]["id"]]

    if due_date := single["due_on"]:
        data["due_date"] = due_date * 1000

    if start_date := single["start_on"]:
        data["start_date"] = start_date * 1000

    token = None
    if member := members.get(single["created_by_id"]):
        token = member["token"]

    task = clickup.get_or_create_task(task_list_id, name, json.dumps(data), token)

    data = dict()

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
        token = None
        if member := members.get(comment["created_by_id"]):
            token = member["token"]

        task_comment_map[comment["id"]] = comment["parent_id"]
        clickup.get_or_create_comment(task["id"], comment["body_plain_text"], token)

    return task, task_comment_map


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


def get_task_tags(name: str) -> list[str]:
    name = name.lower()

    if name == "check project status":
        return ["status"]

    return []


def get_task_status(ac_task: dict) -> str:
    if ac_task["single"]["is_completed"]:
        return "Closed"

    name = ac_task["task_list"]["name"].lower()

    if name in ["inbox", "to do", "project size"]:
        return "Open"

    if name == "in progress":
        return "In progress"

    if name == "done":
        return "Closed"

    return "Open"


def html_to_markdown(html: str) -> str:
    return markdownify(html, heading_style="ATX")


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    clickup = ClickUp(
        secrets["team_id"], secrets["api_token_v1"], secrets["api_tokens_v2"]["default"]
    )

    spaces = import_ac_labels(clickup)
    print()

    members = get_members(clickup, tokens=secrets["api_tokens_v2"])
    print()

    folders, docs, pages, tasks, comment_map = import_ac_projects(
        clickup, spaces, members
    )
    print()

    attachments = import_ac_attachments(clickup, spaces, tasks, comment_map, folders)
    print()
