import json
import logging
import time
from functools import lru_cache

import requests

default_api_version = "v2"

logger = logging.getLogger()


class ClickUp:
    def __init__(self, team_id: int, api_token_v1: str, api_token_v2: str) -> None:
        self.team_id = team_id

        # We can't access dicts until they've been created!
        self.api_urls = {}
        self.api_tokens = {}

        self.api_urls["v1"] = f"https://app.clickup.com"
        self.api_urls["v1_attach"] = f"https://attch.clickup.com/v1"
        self.api_urls["v2"] = f"https://api.clickup.com/api/v2"
        self.api_tokens["v1"] = api_token_v1
        self.api_tokens["v1_attach"] = api_token_v1
        self.api_tokens["v2"] = api_token_v2

    def get(
        self, endpoint: str, params: dict = {}, version: str = default_api_version
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        headers = self.get_headers(version)
        response = requests.get(url, headers=headers, params=params)

        return self._handle_response(response, url, params)

    def _handle_response(
        self, response, url: str, data: dict, files: dict = {}
    ) -> dict:
        response_data = response.json()

        if not response.ok or "ECODE" in response_data:
            log_data = dict(url=url, payload=data, response=response_data)
            if files:
                log_data["files"] = files

            logger.error(log_data)

        return response_data

    def get_api_url(self, version: str = default_api_version) -> str:
        return self.api_urls.get(version, self.api_urls["v2"])

    def get_headers(self, version: str = default_api_version, token: str = "") -> dict:
        if version == default_api_version:
            return dict(
                Authorization=self.get_api_token(version, token),
                Content_Type="application/json",
            )

        return dict(
            Authorization=f"Bearer {self.get_api_token(version)}",
            Content_Type="application/json",
        )

    def get_api_token(self, version: str = default_api_version, token: str = "") -> str:
        if token:
            return token

        return self.api_tokens.get(version, self.api_tokens["v2"])

    def post(
        self,
        endpoint: str,
        payload: dict = {},
        version: str = default_api_version,
        token: str = "",
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        response = requests.post(
            url, headers=self.get_headers(version, token), json=payload
        )

        try:
            test = response.json()
        except:
            # retry since if we're here, the response was not JSON as expected from the API.
            time.sleep(10)
            response = requests.post(
                url, headers=self.get_headers(version, token), json=payload
            )
            time.sleep(10)
        return self._handle_response(response, url, payload)

    def post_multipart(
        self,
        endpoint: str,
        payload: dict = {},
        files: dict = {},
        version: str = default_api_version,
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        response = requests.post(
            url, headers=self.get_headers(version), data=payload, files=files
        )

        return self._handle_response(response, url, payload, files)

    def put(
        self,
        endpoint: str,
        payload: dict = {},
        version: str = default_api_version,
        token: str = "",
    ) -> dict:
        url = f"{self.get_api_url(version)}/{endpoint}"
        response = requests.put(
            url, headers=self.get_headers(version, token), json=payload
        )

        return self._handle_response(response, url, payload)

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

        return {}

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
    def get_folders(self, space: int, archived: bool = False) -> list:
        if archived:
            params = {"archived": "true"}
            return self.get(f"space/{space}/folder", params)["folders"]
        else:
            return self.get(f"space/{space}/folder")["folders"]

    @lru_cache
    def get_or_create_doc(self, parent_id: int, name: str, level: str = "list") -> dict:
        if docs := self.get_views(level, parent_id):
            doc = list(filter(lambda x: x["name"] == name and x["type"] == "doc", docs))
            if doc:
                return doc[0]

        payload = dict(name=name, type="doc", parent=dict(id=parent_id, type=5))

        return self.post(f"list/{parent_id}/view", payload)["view"]

    @lru_cache
    def get_views(self, level: str, parent_id: int) -> list:
        return self.get(f"{level}/{parent_id}/view")["views"]

    # Document page maps to a note in AC
    @lru_cache
    def get_or_create_page(self, doc: str, name: str, body: str) -> dict:
        if pages := self.get_pages(doc):
            page = list(filter(lambda x: x["name"] == name, pages))
            if page:
                return page[0]

        payload = {"name": name, "content": body}

        return self.post(f"docs/v1/view/{doc}/page", payload, "v1")

    @lru_cache
    def get_pages(self, doc: int) -> list:
        pages = self.get(f"docs/v1/view/{doc}/page", version="v1")

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
    def get_templates(self) -> list:
        templates = self.get(f"v1/team/{self.team_id}/templates", version="v1")
        return templates["subcategory"]["templates"]

    def get_lists(self, folder: int) -> list:
        return self.get(f"folder/{folder}/list")["lists"]

    @lru_cache
    def get_list(self, list_id: int) -> dict:
        return self.get(f"list/{list_id}")

    def create_list_from_template(self, folder: int, name: str, template: str) -> dict:
        payload = {
            "category_id": folder,
            "name": name,
            "template_id": template,
            "task_id": None,
            "archived": 0,
            "attachments": True,
            "automation": True,
            "comment": True,
            "comment_attachments": True,
            "content": True,
            "custom_fields": True,
            "external_dependencies": True,
            "include_views": True,
            "internal_dependencies": True,
            "old_assignees": True,
            "old_checklists": True,
            "old_due_date": True,
            "old_followers": True,
            "old_start_date": True,
            "old_status": True,
            "old_statuses": True,
            "old_subtask_assignees": True,
            "old_tags": True,
            "priority": True,
            "recur_settings": True,
            "return_immediately": True,
            "subtasks": True,
            "time_estimate": True,
            "v2_sub_template": True,
        }

        return self.post(
            f"templates/v1/subcategoryTemplate/{template}?v2=true",
            payload=payload,
            version="v1",
        )

    @lru_cache
    def get_or_create_task(
        self, list_id: int, name: str, data: str, token: str = ""
    ) -> dict:
        if tasks := self.get_tasks(list_id):
            task = list(filter(lambda x: x["name"] == name, tasks))
            if task:
                return task[0]

        payload = json.loads(data)
        payload["name"] = name

        return self.post(f"list/{list_id}/task", payload=payload, token=token)

    @lru_cache
    def get_tasks(self, list_id: int) -> list:
        return self.get(f"list/{list_id}/task?include_closed=true")["tasks"]

    # No need to cache this!
    def upload_attachment_to_document(
        self, doc: dict, page: dict, name: str, file_path: str
    ):
        doc_id = doc["id"]
        with open(file_path, "rb") as file:
            files = {
                "attachment": (name, file),
            }
            payload = {"parent": doc_id}
            logger.info(f"Uploading {name} to document {doc_id}")

            return self.post_multipart(
                f"attachment", payload, files, version="v1_attach"
            )

    # No need to cache this!
    def upload_attachment_to_task(self, task: int, name: str, file_path: str):
        with open(file_path, "rb") as file:
            files = {"attachment": (name, file)}
            payload = {"filename": name}
            logger.info(f"Uploading {name} to task {task}")
            return self.post_multipart(f"task/{task}/attachment", payload, files)

    # no need to cache
    def update_task(self, task: int, data: dict) -> dict:
        return self.put(f"task/{task}", payload=data)

    @lru_cache
    def get_or_create_comment(self, task: int, text: str, token: str = "") -> dict:
        if comments := self.get_comments(task):
            if comment := list(filter(lambda x: x["comment_text"] == text, comments)):
                return comment[0]

        payload = dict(comment_text=text)

        return self.post(f"task/{task}/comment", payload=payload, token=token)

    @lru_cache
    def get_comments(self, task: int) -> list:
        return self.get(f"task/{task}/comment")["comments"]

    @lru_cache
    def get_custom_fields(self, list_id: int) -> list:
        return self.get(f"list/{list_id}/field")["fields"]

    def set_custom_field(self, task: int, field: str, value) -> dict:
        return self.post(f"task/{task}/field/{field}", payload=dict(value=value))

    def create_time_entry(self, data: dict) -> dict:
        return self.post(f"team/{self.team_id}/time_entries", payload=data)
