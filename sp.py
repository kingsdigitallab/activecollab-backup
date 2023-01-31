import argparse
import csv
import json
import logging
from datetime import datetime

from tqdm import tqdm
from urlextract import URLExtract

from clickup import ClickUp

extractor = URLExtract()
logging.basicConfig(
    filemode="w",
    filename="sp.log",
    format="%(levelname)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger()


def update_project_data(clickup: ClickUp, project_ids: list, projects: dict):
    if project_ids:
        for folder_id in tqdm(project_ids, desc="Projects"):
            folder = clickup.get_folder(folder_id)
            update_project(clickup, folder, projects)
    else:
        spaces = clickup.get_spaces()
        for space in tqdm(spaces, desc="Spaces"):
            logger.info(f"Space {space['name']}")

            folders = clickup.get_folders(space["id"], archived=True)
            for folder in tqdm(folders, desc="Projects", leave=False):
                update_project(clickup, folder, projects)


def update_project(clickup: ClickUp, folder: dict, projects: dict):
    logger.info(f"Project {folder['name']}")

    for l in folder["lists"]:
        if l["name"] == "_Metadata":
            metadata = clickup.get_list(l["id"])
            for task in clickup.get_tasks(metadata["id"]):
                if folder["name"].startswith(task["name"]):
                    update_task(clickup, folder, task, projects)


def update_task(
    clickup: ClickUp, folder: dict, task: dict, projects: dict
):
    ac_project_id_field = filter(
        lambda x: x["name"] == "AC project ID", task["custom_fields"]
    )
    if not ac_project_id_field:
        logger.warning(f"AC project ID not found for project {folder['name']}")
        return

    ac_project_id = list(ac_project_id_field)[0].get("value")
    if ac_project_id not in projects:
        logger.warning(
            f"Project {ac_project_id}: {folder['name']} not found in Sharepoint"
        )
        return

    data = projects[ac_project_id]

    for field in task["custom_fields"]:
        field_name = field["name"].strip()
        field_value = field.get("value", None)
        if field_name in data:
            value = data[field_name]
            if value and not field_value:
                update_field(clickup, task, field, value)


def update_field(clickup: ClickUp, task: dict, field: dict, data: str):
    field_type = field["type"]

    data = data.strip()
    value = data

    if field_type == "currency":
        value = float(data.replace("£", "").replace(",", ""))
    elif field_type == "date":
        value = datetime.strptime(data, "%d/%m/%Y").timestamp() * 1000
    elif field_type in ["drop_down", "labels"]:
        field_value = "name"
        if field_type == "labels":
            field_value = "label"

        if found := find_value(field, field_value, data):
            value = found[0].get("id")
        else:
            logger.error(f"Value {data} not found for field {field['name']}")
            return

        if field_type == "labels":
            value = [value]
    elif field_type == "url":
        value = value.replace("&%2358;", ":")
        value = list(set(extractor.find_urls(value)))
        value = value[0] if value else ""

    clickup.set_custom_field(task["id"], field["id"], value)


def find_value(field: dict, field_value: str, data: str):
    data = data.lower()

    # Project size
    if field["id"] in [
        "93a69e6d-c45a-4a2a-ba74-601772a671c8",
        "ce5f3fed-6492-456e-8e63-ef329536abad",
    ]:
        return list(
            filter(
                lambda x: x[field_value].strip().lower().startswith(data),
                field["type_config"]["options"],
            )
        )

    return list(
        filter(
            lambda x: x[field_value].strip().lower() == data,
            field["type_config"]["options"],
        )
    )


if __name__ == "__main__":
    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    clickup = ClickUp(
        secrets["team_id"], secrets["api_token_v1"], secrets["api_tokens_v2"]["default"]
    )

    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--projects", help="ClickUp folder ids (projects) to import, comma separated")
    arguments = parser.parse_args()

    project_ids = None
    if arguments.projects:
        project_ids = arguments.projects.split(",")

    with open("data/sp.csv", "r") as f:
        spreader = csv.DictReader(f)
        projects = {
            row["AC project ID"]: {k.strip(): v for k, v in row.items()}
            for row in spreader
        }

    update_project_data(clickup, project_ids, projects)