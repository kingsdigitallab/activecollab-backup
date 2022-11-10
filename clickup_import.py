import json
import os
from datetime import datetime

from clickup import ClickUp


def import_ac_labels(click_up: ClickUp, path: str = "data/labels.json") -> None:
    print("Importing AC labels")

    with open(path, "r") as f:
        ac_labels = json.load(f)

    spaces = {}

    for label in ac_labels:
        space = click_up.get_or_create_space(label["name"])
        print(f"- {space['name']}")

        spaces[label["id"]] = space

    return spaces


def import_ac_projects(click_up: ClickUp, spaces: dict, path: str = "data") -> None:
    print("Importing AC projects")

    with open(os.path.join(path, "projects.json"), "r") as f:
        ac_projects = json.load(f)

    folders = {}
    docs = {}

    for project in ac_projects:
        space = spaces[project["label_id"]]["id"]

        folder = click_up.get_or_create_folder(space, project["name"])
        folders[project["id"]] = folder
        print(f"- {folder['name']}")

        doc = click_up.get_or_create_doc(folder["id"], "Documents")
        page = click_up.get_or_create_page(doc["id"], "About", project["body"])
        docs[project["id"]] = doc

        task_list = click_up.get_or_create_list(folder["id"], "Tasks")

        # Import notes/documents!
        # Important fields are: name, body_plain_text, created_by_id, created_by_name
        with open(
            os.path.join(path, "projects", str(project["id"]), "notes.json")
        ) as f:
            project_notes = json.load(f)

        for note in project_notes:
            body = f"Originally created by {note['created_by_name']}"
            body = f"{body} on {getDate(note['created_on'])}"
            body = f"{body}\n\n---\n\n{note['body_plain_text']}"
            click_up.get_or_create_page(doc["id"], note["name"], body)

        # import tasks
        with open(
            os.path.join(path, "projects", str(project["id"]), "tasks.json")
        ) as f:
            project_tasks = json.load(f)


def getDate(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d, %H:%M:%S")


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    click_up = ClickUp(
        secrets["team_id"], secrets["api_token_v1"], secrets["api_token_v2"]
    )

    spaces = import_ac_labels(click_up)
    print()

    projects = import_ac_projects(click_up, spaces)
    print()

    # space = click_up.create_space("API test Test")
    # print(space)

    # spaces = dict()
    # for space in click_up.get("space")["spaces"]:
    #     spaces[space["name"].lower()] = space

    # for k, v in spaces.items():
    #     print(k)
