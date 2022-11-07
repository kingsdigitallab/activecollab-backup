import json
import requests


class ClickUp:
    def __init__(self, team_id: int, api_token: str) -> None:
        self.team_id = team_id
        self.api_url = f"https://api.clickup.com/api/v2/team/{self.team_id}"
        self.api_token = api_token

    @property
    def headers(self) -> dict:
        return dict(Authorization=self.api_token, Content_Type="application/json")

    def get(self, endpoint: str, params: dict = None) -> dict:
        url = f"{self.api_url}/{endpoint}"
        response = requests.get(url, headers=self.headers, params=params)
        return response.json()

    def post(self, endpoint: str, payload: dict = None) -> dict:
        url = f"{self.api_url}/{endpoint}"
        response = requests.post(url, headers=self.headers, json=payload)
        return response.json()

    def create_space(self, name: str) -> dict:
        payload = dict(name=name.capitalize())
        space = self.post("space", payload)
        return space


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    click_up = ClickUp(secrets["team_id"], secrets["api_token"])
    space = click_up.create_space("API test Test")
    print(space)

    spaces = dict()
    for space in click_up.get("space")["spaces"]:
        spaces[space["name"].lower()] = space

    for k, v in spaces.items():
        print(k)
