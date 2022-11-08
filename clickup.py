import json
import requests
from functools import lru_cache


class ClickUp:
    _team = None

    def __init__(self, team_id: int, api_token: str) -> None:
        self.team_id = team_id
        self.api_url = f"https://api.clickup.com/api/v2/team/{self.team_id}"
        self.api_token = api_token

    @property
    def headers(self) -> dict:
        return dict(Authorization=self.api_token, Content_Type="application/json")

    @property
    def team(self):
        if not self._team:
            self._team = self.get("")["team"]

        return self._team

    def get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.api_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def post(self, endpoint: str, payload: dict = None) -> dict:
        url = f"{self.api_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def get_member(self, email: str) -> dict:
        found = list(
            filter(lambda x: x["user"]["email"] == email, self.team["members"])
        )
        if found:
            return found[0]

        # return default user
        return list(
            filter(
                lambda x: x["user"]["email"] == "kdl-support@kcl.ac.uk",
                self.team["members"],
            )
        )[0]

    @lru_cache
    def get_space(self, name: str) -> dict:
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
        space = self.post("space", payload)

        return space

    @lru_cache
    def get_spaces(self) -> dict:
        return self.get("space")["spaces"]

    @lru_cache
    def get_folder(self, space: int, name: str) -> dict:
        if folders := self.get_folders(space):
            folder = list(filter(lambda x: x["name"] == name, folders))
            if folder:
                return folder[0]

        payload = dict(name=name)
        folder = self.post(f"../../space/{space}/folder", payload)

        return folder

    @lru_cache
    def get_folders(self, space: int) -> dict:
        return self.get(f"../../space/{space}/folder")["folders"]


def import_ac_labels(click_up: ClickUp, path: str = "data/labels.json") -> None:
    print("Importing AC labels")

    with open(path, "r") as f:
        ac_labels = json.load(f)

    spaces = {}

    for label in ac_labels:
        space = click_up.get_space(label["name"])
        print(f"- {space['name']}")

        spaces[label["id"]] = space

    return spaces


def import_ac_projects(
    click_up: ClickUp, spaces: dict, path: str = "data/projects.json"
) -> None:
    print("Importing AC projects")

    with open(path, "r") as f:
        ac_projects = json.load(f)

    folders = {}

    for project in ac_projects:
        space = spaces[project["label_id"]]["id"]
        folder = click_up.get_folder(space, project["name"])
        print(f"- {folder['name']}")

        folders[project["id"]] = folder


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    click_up = ClickUp(secrets["team_id"], secrets["api_token"])

    spaces = import_ac_labels(click_up)
    print()

    import_ac_projects(click_up, spaces)
    print()

    # space = click_up.create_space("API test Test")
    # print(space)

    # spaces = dict()
    # for space in click_up.get("space")["spaces"]:
    #     spaces[space["name"].lower()] = space

    # for k, v in spaces.items():
    #     print(k)
