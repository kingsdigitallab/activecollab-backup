import json
from functools import lru_cache


import requests

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

        print(f"--- GET {url}")

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
        print(f"--- POST {url}")
        response = requests.post(url, headers=self.get_headers(version), json=payload)
        return response.json()

    def post_multipart(
        self, endpoint: str, payload: dict = None, files: dict = None, version: str = default_api_version
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        print(f"--- POST {url}")
        response = requests.post(url, headers=self.get_headers(version), json=payload, files=files)
        return response.json()

    def put(
        self, endpoint: str, payload: dict = None, version: str = default_api_version
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        print(f"--- PUT {url}")
        response = requests.put(url, headers=self.get_headers(version), json=payload)
        return response.json()

    @lru_cache
    def get_team(self):
        return self.get(f"team/{self.team_id}")["team"]

    @lru_cache
    def get_member(self, email: str) -> dict:
        found = list(
            filter(lambda x: x["user"]["email"] == email, self.get_team()["members"])
        )
        if found:
            return found[0]

        return None

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
        return self.post(f"team/{self.team_id}/space", payload)

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
        return self.post(f"space/{space}/folder", payload)

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
        return self.post(f"folder/{folder}/view", payload)["view"]

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
        return self.post(f"view/{doc}/page", payload, "v1")

    @lru_cache
    def get_pages(self, doc: int) -> list:
        pages = self.get(f"view/{doc}/page", version="v1")
        return pages["pages"]

    @lru_cache
    def get_or_create_list(self, folder: int, name: str) -> dict:
        if lists := self.get_lists(folder):
            l = list(filter(lambda x: x["name"] == name, lists))
            if l:
                return l[0]

        payload = dict(name=name)
        return self.post(f"folder/{folder}/list", payload)

    @lru_cache
    def get_lists(self, folder: int) -> list:
        return self.get(f"folder/{folder}/list")["lists"]

    @lru_cache
    def get_or_create_task(self, list_id: int, name: str, data: str) -> dict:
        if tasks := self.get_tasks(list_id):
            task = list(filter(lambda x: x["name"] == name, tasks))
            if task:
                return task[0]

        payload = json.loads(data)
        payload["name"] = name

        return self.post(f"list/{list_id}/task", payload)

    @lru_cache
    def get_tasks(self, list_id: int) -> list:
        return self.get(f"list/{list_id}/task")["tasks"]

    # No need to cache this!
    def upload_attachment_to_task(self, task: int, name: str, file_path: str) -> dict:
        with open(file_path, "rb") as file:
            files = {
                "attachment": (name, file)
            }
            payload = {
                "filename": name
            }
            print(f"Uploading {name} to task {task}")
            self.post_multipart(f"task/{task}/attachment", payload, files)


    # no need to cache
    def update_task(self, task: int, data: dict) -> dict:
        return self.put(f"task/{task}", payload=data)