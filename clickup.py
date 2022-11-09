import json
import os
import requests
from datetime import datetime
from functools import lru_cache

default_api_version = "v2"


class ClickUp:
    def __init__(self, team_id: int, api_token_v1: str, api_token_v2: str) -> None:
        self.team_id = team_id

        # We can't access dicts until they've been created!
        self.api_urls = {}
        self.api_tokens = {}

        self.api_urls["v1"] = f"https://app.clickup.com/docs/v1"
        self.api_urls["v2"] = f"https://api.clickup.com/api/v2"
        self.api_tokens["v1"] = api_token_v1
        self.api_tokens["v2"] = api_token_v2

    def get(
        self, endpoint: str, params: dict = None, version: str = default_api_version
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        headers = self.get_headers(version)

        print(f"GET {url}")
        print(f"Headers {headers}")

        response = requests.get(url, headers=headers, params=params)
        return response.json()

    def get_api_url(self, version: str = default_api_version) -> str:
        return self.api_urls.get(version)

    def get_headers(self, version: str = default_api_version) -> dict:
        if version == default_api_version:
            return dict(
                Authorization=self.get_api_token(version),
                Content_Type="application/json",
            )

        return dict(
            Authorization=f"Bearer {self.get_api_token(version)}",
            Content_Type="application/json",
        )

    def get_api_token(self, version: str = default_api_version) -> str:
        return self.api_tokens.get(version)

    def post(
        self, endpoint: str, payload: dict = None, version: str = default_api_version
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        print(f"POST {url}")
        response = requests.post(url, headers=self.get_headers(version), json=payload)
        return response.json()

    @lru_cache
    def get_team(self):
        return self.get(f"team/{self.team_id}/team")["team"]

    @lru_cache
    def get_member(self, email: str) -> dict:
        found = list(
            filter(lambda x: x["user"]["email"] == email, self.get_team()["members"])
        )
        if found:
            return found[0]

        # return default user
        return list(
            filter(
                lambda x: x["user"]["email"] == "kdl-support@kcl.ac.uk",
                self.get_team()["members"],
            )
        )[0]

    @lru_cache
    def get_or_create_space(self, name: str) -> dict:
        name = name.capitalize()

        space = list(filter(lambda x: x["name"] == name, self.get_spaces()))
        if space:
            return space[0]

        payload = {
            "name": name,
            "multiple_assignees": True,
            "features": {
                "due_dates": {
                    "enabled": True,
                    "start_date": True,
                    "remap_due_dates": True,
                    "remap_closed_due_date": False,
                },
                "time_tracking": {"enabled": True},
                "tags": {"enabled": True},
                "time_estimates": {"enabled": True},
                "checklists": {"enabled": True},
                "custom_fields": {"enabled": True},
                "remap_dependencies": {"enabled": True},
                "dependency_warning": {"enabled": True},
                "portfolios": {"enabled": True},
            },
        }
        space = self.post(f"team/{self.team_id}/space", payload)

        return space

    @lru_cache
    def get_spaces(self) -> dict:
        return self.get(f"team/{self.team_id}/space")["spaces"]

    @lru_cache
    def get_or_create_folder(self, space: int, name: str) -> dict:
        if folders := self.get_folders(space):
            folder = list(filter(lambda x: x["name"] == name, folders))
            if folder:
                return folder[0]

        payload = dict(name=name)
        folder = self.post(f"space/{space}/folder", payload)

        return folder

    @lru_cache
    def get_folders(self, space: int) -> dict:
        return self.get(f"space/{space}/folder")["folders"]

    @lru_cache
    def get_or_create_doc(self, folder: int, name: str) -> dict:
        if docs := self.get_folder_views(folder):
            doc = list(filter(lambda x: x["name"] == name and x["type"] == "doc", docs))
            if doc:
                return doc[0]

        payload = dict(name=name, type="doc", parent=dict(id=folder, type=5))
        doc = self.post(f"folder/{folder}/view", payload)["view"]

        return doc

    @lru_cache
    def get_folder_views(self, folder: int) -> list:
        return self.get(f"folder/{folder}/view")["views"]

    # Document page maps to a note in AC
    @lru_cache
    def get_or_create_page(self, doc: str, name: str, body: str) -> dict:
        if pages := self.get_pages(doc):
            page = list(filter(lambda x: x["name"] == name, pages))
            if page:
                return page[0]

        payload = {"name": name, "content": body}
        page = self.post(f"view/{doc}/page", payload, "v1")

        return page

    @lru_cache
    def get_pages(self, doc: int) -> list:
        pages = self.get(f"view/{doc}/page", version="v1")
        return pages["pages"]


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
        with open(os.path.join(path, "projects", str(project["id"]), "tasks.json") as f:
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
