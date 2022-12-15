import csv
import json
import locale
import logging
import os
import re
from datetime import datetime
from glob import glob
from time import sleep
from typing import Optional
import argparse

from markdownify import markdownify
from pythonjsonlogger import jsonlogger
from tqdm import tqdm

from clickup import ClickUp

locale.setlocale(locale.LC_ALL, "en_GB.UTF-8")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
handler = logging.FileHandler(filename="clickup_import.json", mode="w")
handler.setFormatter(jsonlogger.JsonFormatter())
logger.addHandler(handler)

limit_projects = False
import_attachments = True
limit_projects_resume = []
ac_user_initials = {}
project_mappings = {}



def import_ac_labels(clickup: ClickUp, path: str = "data/labels.json") -> dict:
    logger.info("Importing AC labels")

    with open(path, "r") as f:
        ac_labels = json.load(f)

    spaces = {}

    for label in tqdm(ac_labels, desc="Labels"):
        space = clickup.get_or_create_space(label["name"])
        logger.info(f"- {space['name']}")

        spaces[label["id"]] = space

    return spaces


def get_members(
    clickup: ClickUp, path: str = "data/users.json", tokens: dict = {}
) -> dict:
    with open(path, "r") as f:
        ac_users = json.load(f)

        for user in ac_users:
            ac_user_initials[user["id"]] = user["short_display_name"]

    members = dict(ac=ac_users)

    for user in tqdm(ac_users, desc="Members"):
        id = user["id"]
        members[f"ac_{id}"] = user
        if member := clickup.get_member(user["email"]):
            members[id] = member
            members[id]["token"] = tokens.get(user["email"], tokens.get("default"))

    return members


def import_ac_attachments(
    clickup: ClickUp, tasks: dict, comment_map: dict, folders: dict, path: str = "data"
) -> None:
    logger.info("Importing AC Attachments")

    projects_json = glob((os.path.join(path, "attachments", "*.json")))
    for project_json in tqdm(projects_json, desc="Attachments"):
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
                        clickup.upload_attachment_to_task(task, a_name, file_path)
                        continue

                    elif attachment["parent_type"] == "Comment":
                        # Was attached to comment, attach to task
                        task = tasks[comment_map[attachment["parent_id"]]]["id"]
                        clickup.upload_attachment_to_task(task, a_name, file_path)
                        continue

                # It was somewhere else, attach to an "AC Imported Attachments" task
                # in the metadata list

                folder = folders[attachment["project_id"]]
                task_list = clickup.get_or_create_list(folder["id"], "_Metadata")

                data = {}
                task = clickup.get_or_create_task(
                    task_list["id"], "ActiveCollab attachments", json.dumps(data)
                )
                clickup.upload_attachment_to_task(task["id"], a_name, file_path)
                continue


def import_ac_projects(
    clickup: ClickUp, spaces: dict, members: dict, path: str = "data"
) -> tuple:
    logger.info("Importing AC projects")

    with open(os.path.join(path, "projects.json"), "r") as f:
        ac_projects = json.load(f)
    
    with open(os.path.join(path, "archived_projects.json"), "r") as f:
        archived_projects = json.load(f)

    with open(os.path.join(path, "companies.json"), "r") as f:
        companies = json.load(f)

    with open(os.path.join(path, "job_types.json"), "r") as f:
        job_types = json.load(f)
        job_types = {item["id"]: item for item in job_types}

    folders = {}
    lists = {}
    docs = {}
    pages = {}
    tasks = {}
    comment_map = {}

    for project in tqdm(ac_projects, desc="Projects", position=0):

        if limit_projects and str(project["id"]) not in limit_projects:
            continue
        print("Importing project: {0}".format(str(project["id"])))
        project_path = os.path.join(path, "projects", str(project["id"]))

        space = spaces[project["label_id"]]["id"]

        folder = clickup.get_or_create_folder(space, project["name"])
        folders[project["id"]] = folder
        folder_name = folder["name"]
        logger.info(f"- {folder_name}")

        acronym = re.split(r"[\[\(:;]", folder_name)[0].strip()

        task_list = clickup.get_or_create_list(folder["id"], "_Metadata")
        import_project_details(
            project_path, clickup, task_list["id"], project, acronym, companies
        )
        lists[project["id"]] = task_list

        logger.info("-- Import notes")
        doc = clickup.get_or_create_doc(task_list["id"], "Documents")
        page = import_ac_note(clickup, doc["id"], "About", project["body"])
        docs[project["id"]] = doc

        # Import notes/documents!
        # Important fields are: name, body_plain_text, created_by_id, created_by_name
        with open(os.path.join(project_path, "notes.json")) as f:
            project_notes = json.load(f)

        for note in tqdm(project_notes, desc="Notes", position=1, leave=False):
            body = f"Originally created by {note['created_by_name']}"
            body = f"{body} on {get_date(note['created_on'])}"
            body = f"{body}\n\n---\n\n{note['body_plain_text']}"

            page = import_ac_note(clickup, doc["id"], note["name"], body)
            pages[note["id"]] = page

        with open(os.path.join(project_path, "project.json")) as f:
            hourly_rates = json.load(f)["hourly_rates"]

        with open(os.path.join(project_path, "time-records.json")) as f:
            time_records = json.load(f)["time_records"]

        with open(os.path.join(project_path, "tasks.json")) as f:
            project_tasks = json.load(f)

        # import tasks
        logger.info("-- Import tasks")
        task_data = prepare_task_data(
            acronym, project_tasks, time_records, job_types, hourly_rates, project
        )

        for list_name in tqdm(task_data.keys(), desc="Lists", position=1, leave=False):
            template = "t-212487909"
            if "pre-project" in list_name:
                template = "t-212487803"

            folder_lists = clickup.get_lists(folder["id"])
            if found := list(filter(lambda x: x["name"] == list_name, folder_lists)):
                task_list = found[0]
            else:
                task_list = clickup.create_list_from_template(
                    folder["id"], list_name, template
                )
                task_list = clickup.get_list(task_list["id"])
                sleep(10)

            task_list_id = task_list["id"]

            for pt in tqdm(
                task_data[list_name]["tasks"], desc="Tasks", position=2, leave=False
            ):
                ac_task_id = pt["id"]
                logger.debug(f"--- Importing AC task {ac_task_id}")

                if ac_task_id:
                    if pt["is_completed"]:
                        task_path = os.path.join(
                            project_path, "tasks/archived", str(ac_task_id)
                        )
                    else:
                        task_path = os.path.join(project_path, "tasks", str(ac_task_id))
                    try:
                        with open(os.path.join(task_path, "tasks.json"), "r") as f:
                            ac_task = json.load(f)

                        task, task_comment_map = import_ac_task(
                            clickup,
                            task_list_id,
                            ac_task,
                            members,
                            hourly_rates,
                            pt["rate"],
                        )
                        tasks[ac_task["single"]["id"]] = task

                        if task_comment_map is not None:
                            comment_map = comment_map | task_comment_map
                    except:
                        # If we got here, task info was missing. Log for correction:
                        with open("data.missing", 'a+') as f:
                            f.write("{0}:{1}".format(project["id"], ac_task_id))
                        continue
                else:
                    ac_task = dict(
                        single=dict(
                            assignee_id=0,
                            body="",
                            created_by_id=-1,
                            due_on=0,
                            estimate=0,
                            is_completed=project["is_completed"],
                            is_important=False,
                            job_type_id=-1,
                            name="ActiveCollab project time entries",
                            start_on=0,
                        ),
                        comments=[],
                        subscribers=[],
                        subtasks=[],
                        task_list=dict(name="inbox"),
                        tracked_time=1,
                    )
                    task, _ = import_ac_task(
                        clickup,
                        task_list_id,
                        ac_task,
                        members,
                        hourly_rates,
                        pt["rate"],
                    )

                for record in tqdm(
                    pt["time_records"], desc="Time", position=3, leave=False
                ):
                    data = dict(
                        description=record["summary"],
                        start=record["ts"],
                        billable=record["billable_status"] == 1,
                        duration=record["value"],
                        assignee=get_assignee(members, record["created_by_id"])["user"][
                            "id"
                        ],
                        tid=task["id"],
                        tags=[
                            dict(name="activecollab"),
                            dict(name=ac_user_initials[record["created_by_id"]]),
                            dict(name=record["tag"]),
                        ],
                    )
                    resp = clickup.create_time_entry(data)

        if limit_projects:
            limit_projects_resume.remove(str(project["id"]))
            print("To resume: -l {0}".format(",".join(limit_projects_resume)))

    for project in tqdm(archived_projects, desc="Projects", position=0):
        if limit_projects and str(project["id"]) not in limit_projects:
            continue
        print("Importing project: {0}".format(str(project["id"])))
        project_path = os.path.join(path, "projects/archived", str(project["id"]))

        space = spaces[project["label_id"]]["id"]

        folder = clickup.get_or_create_folder(space, project["name"])
        folders[project["id"]] = folder
        folder_name = folder["name"]
        logger.info(f"- {folder_name}")

        acronym = re.split(r"[\[\(:;]", folder_name)[0].strip()

        task_list = clickup.get_or_create_list(folder["id"], "_Metadata")
        import_project_details(
            project_path, clickup, task_list["id"], project, acronym, companies
        )
        lists[project["id"]] = task_list

        logger.info("-- Import notes")
        doc = clickup.get_or_create_doc(task_list["id"], "Documents")
        page = import_ac_note(clickup, doc["id"], "About", project["body"])
        docs[project["id"]] = doc

        # Import notes/documents!
        # Important fields are: name, body_plain_text, created_by_id, created_by_name
        with open(os.path.join(project_path, "notes.json")) as f:
            project_notes = json.load(f)

        for note in tqdm(project_notes, desc="Notes", position=1, leave=False):
            body = f"Originally created by {note['created_by_name']}"
            body = f"{body} on {get_date(note['created_on'])}"
            body = f"{body}\n\n---\n\n{note['body_plain_text']}"

            page = import_ac_note(clickup, doc["id"], note["name"], body)
            pages[note["id"]] = page

        with open(os.path.join(project_path, "project.json")) as f:
            hourly_rates = json.load(f)["hourly_rates"]

        with open(os.path.join(project_path, "time-records.json")) as f:
            time_records = json.load(f)["time_records"]

        with open(os.path.join(project_path, "tasks.json")) as f:
            project_tasks = json.load(f)

        # import tasks
        logger.info("-- Import tasks")
        task_data = prepare_task_data(
            acronym, project_tasks, time_records, job_types, hourly_rates, project
        )

        for list_name in tqdm(task_data.keys(), desc="Lists", position=1, leave=False):
            template = "t-212487909"
            if "pre-project" in list_name:
                template = "t-212487803"

            folder_lists = clickup.get_lists(folder["id"])
            if found := list(filter(lambda x: x["name"] == list_name, folder_lists)):
                task_list = found[0]
            else:
                task_list = clickup.create_list_from_template(
                    folder["id"], list_name, template
                )
                task_list = clickup.get_list(task_list["id"])
                sleep(10)

            task_list_id = task_list["id"]

            for pt in tqdm(
                task_data[list_name]["tasks"], desc="Tasks", position=2, leave=False
            ):
                ac_task_id = pt["id"]
                logger.debug(f"--- Importing AC task {ac_task_id}")

                if ac_task_id:
                    if pt["is_completed"]:
                        task_path = os.path.join(
                            project_path, "tasks/archived"
                        )
                    else:
                        task_path = os.path.join(project_path, "tasks")
                    try:
                        with open(os.path.join(task_path, "{0}.json".format(str(ac_task_id))), "r") as f:
                            ac_task = json.load(f)
                    except:
                        # If we got here, task info was missing. Log for correction:
                        with open("data.missing", 'a+') as f:
                            f.write("{0}:{1}".format(project["id"], ac_task_id))
                        continue

                    task, task_comment_map = import_ac_task(
                        clickup,
                        task_list_id,
                        ac_task,
                        members,
                        hourly_rates,
                        pt["rate"],
                    )
                    tasks[ac_task["single"]["id"]] = task

                    if task_comment_map is not None:
                        comment_map = comment_map | task_comment_map
                else:
                    ac_task = dict(
                        single=dict(
                            assignee_id=0,
                            body="",
                            created_by_id=-1,
                            due_on=0,
                            estimate=0,
                            is_completed=project["is_completed"],
                            is_important=False,
                            job_type_id=-1,
                            name="ActiveCollab project time entries",
                            start_on=0,
                        ),
                        comments=[],
                        subscribers=[],
                        subtasks=[],
                        task_list=dict(name="inbox"),
                        tracked_time=1,
                    )
                    task, _ = import_ac_task(
                        clickup,
                        task_list_id,
                        ac_task,
                        members,
                        hourly_rates,
                        pt["rate"],
                    )

                for record in tqdm(
                    pt["time_records"], desc="Time", position=3, leave=False
                ):
                    data = dict(
                        description=record["summary"],
                        start=record["ts"],
                        billable=record["billable_status"] == 1,
                        duration=record["value"],
                        assignee=get_assignee(members, record["created_by_id"])["user"][
                            "id"
                        ],
                        tid=task["id"],
                        tags=[
                            dict(name="activecollab"),
                            dict(name=ac_user_initials[record["created_by_id"]]),
                            dict(name=record["tag"]),
                        ],
                    )
                    resp = clickup.create_time_entry(data)

        if limit_projects:
            limit_projects_resume.remove(str(project["id"]))
            print("To resume: -l {0}".format(",".join(limit_projects_resume)))

    return folders, lists, docs, pages, tasks, comment_map


def import_project_details(
    project_path: str,
    clickup: ClickUp,
    task_list_id: int,
    project: dict,
    acronym: str,
    companies: list,
) -> tuple[dict, dict]:
    task_details = None
    task_budget = None

    if companies := list(filter(lambda x: x["id"] == project["company_id"], companies)):
        logger.info("-- Import project details")
        details = {"Partner organisation(s)": "King's College, London"}
        faculty, department = companies[0]["name"].split(":")
        details["Faculty"] = faculty.strip()
        details["Department(s)"] = department.strip()

        if faculty == "External":
            details["Partner organisation(s)"] = ""
        if faculty == "KCL":
            details["Faculty"] = ""
        if faculty == "King's":
            details["Faculty"] = details["Department(s)"]
            details["Department(s)"] = ""

        custom_fields = [
            # faculty
            dict(id="4c0f85e5-e82d-4980-b511-de41cefd6163", value=0),
            # department
            dict(id="342f55be-f7b0-4508-8242-2d573696e299", value=[]),
            # partner organisation
            dict(id="d98a262e-632d-4b9f-8776-520fbe5b29ee", value=[]),
            # ac project id
            dict(id="1fabc62c-b9b9-42ef-b3f3-0158f2106ae2", value=str(project["id"])),
            # spend
            dict(id="b05c5fb3-d3b6-4cd4-bf37-e3142666f051", value=0),
        ]

        data = dict(
            description="",
            assignees=[],
            tags=["_meta", "details"],
            status="Open",
            priority=None,
            due_date_time=False,
            time_estimate=None,
            start_date_time=False,
            custom_fields=custom_fields,
        )

        task_details = clickup.get_or_create_task(
            task_list_id, acronym, json.dumps(data)
        )

        fields = clickup.get_custom_fields(task_list_id)
        if fields and len(fields) > 0:
            for key, value in details.items():
                if field := list(filter(lambda x: x["name"] == key, fields)):
                    field = field[0]

                if field_options := list(
                    filter(
                        lambda x: x.get("name") == value or x.get("label") == value,
                        field["type_config"]["options"],
                    )
                ):
                    field_value = list(map(lambda x: x["id"], field_options))
                    if key == "Faculty":
                        field_value = field_value[0]
                    try:
                        clickup.set_custom_field(
                            task_details["id"], field["id"], field_value
                        )
                    except:
                        pass

    with open(os.path.join(project_path, "expenses.json")) as f:
        expenses = json.load(f)["expenses"]

    expenses = []
    spend = 0
    if expenses:
        spend = sum(map(lambda x: x["value"], expenses))
        expenses = map(
            lambda x: (
                f"- _{get_date(x['record_date'])}_, "
                f"{x['summary']}: **{locale.currency(x['value'])}**"
            ),
            expenses,
        )

    custom_fields = [
        # overall budget
        dict(id="3dcddcd7-4a5b-4380-95c8-1154a9ce8ff8", value=project["budget"]),
        # other expenses spend
        dict(id="6e5a4048-e1ee-4ed8-b4b6-ffb54675fb5a", value=spend),
    ]

    expenses_str = "\n".join(expenses)
    data = dict(
        markdown_description=f"## Expenses\n{expenses_str}",
        assignees=[],
        tags=["_meta", "budget"],
        status="Open",
        priority=None,
        due_date_time=False,
        time_estimate=None,
        start_date_time=False,
        custom_fields=custom_fields,
    )

    task_budget = clickup.get_or_create_task(
        task_list_id, "Project budget", json.dumps(data)
    )

    return task_details, task_budget


def get_date(timestamp: int) -> str:
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%Y-%m-%d, %H:%M:%S")


def import_ac_note(clickup: ClickUp, doc: str, name: str, body: str) -> dict:
    return clickup.get_or_create_page(doc, name, body)


def prepare_task_data(
    list_name: str, tasks: dict, records: list, job_types: dict, hourly_rates: dict, project: dict
) -> dict:
    prepared_time_records = prepare_time_records(
        list_name, records, job_types, hourly_rates, project
    )

    with open("prepared_time_records.json", "w") as f:
        json.dump(prepared_time_records, f)

    _tasks = []
    for task in [*tasks["tasks"], *tasks["completed_task_ids"]]:
        if type(task) == int:
            _tasks.append(dict(id=task, is_completed=True))
        else:
            _tasks.append(dict(id=task["id"], is_completed=False))

    prepared_tasks = []
    for task in _tasks:
        found = filter(lambda x: x["task_id"] == task["id"], prepared_time_records)

        pt = {**task, "list_names": [], "time_records": []}

        for tr in found:
            pt["list_names"].append(tr["list_name"])
            pt["time_records"].append(tr)
        else:
            if len(prepared_time_records):
                pt["list_names"].append(prepared_time_records[-1]["list_name"])
            else:
                pt["list_names"].append(project["name"])

        pt["list_names"] = list(set(pt["list_names"]))
        
        prepared_tasks.append(pt)

    with open("prepared_tasks.json", "w") as f:
        json.dump(prepared_tasks, f)

    list_names = set([tr["list_name"] for tr in prepared_time_records])
    if not len(list_names):
        list_names = set([pt["list_names"][0] for pt in prepared_tasks])

    prepared_data = {}

    for ln in list_names:
        prepared_data[ln] = {}
        prepared_data[ln]["tasks"] = []
        for t in filter(lambda x: ln in x["list_names"], prepared_tasks):
            task = {**t}
            task["time_records"] = list(
                filter(lambda x: x["list_name"] == ln, t["time_records"])
            )
            task["rate"] = (
                task["time_records"][0]["rate"] if len(task["time_records"]) else -1
            )
            prepared_data[ln]["tasks"].append(task)

        time_records_without_task = {
            "id": None,
            "time_records": list(
                filter(
                    lambda x: x["task_id"] == None and x["list_name"] == ln,
                    prepared_time_records,
                )
            ),
        }
        time_records_without_task["rate"] = (
            time_records_without_task["time_records"][0]["rate"]
            if len(time_records_without_task["time_records"])
            else -1
        )
        prepared_data[ln]["tasks"].append(time_records_without_task)

    with open("prepared_data.json", "w") as f:
        json.dump(prepared_data, f)

    return prepared_data


def prepare_time_records(
    list_name: str, records: list, job_types: dict, hourly_rates: dict, project: dict
) -> list:
    records = sorted(records, key=lambda x: x["record_date"])
    time_records = []
    for record in records:
        job_type_id = record["job_type_id"]
        job_type = job_types[job_type_id]["name"]
        hourly_rate = hourly_rates[str(job_type_id)] if project["is_billable"] else 0
        rounded_hourly_rate = round(hourly_rate)

        name = rounded_hourly_rate
        if job_type == "pre-project":
            name = job_type

        if rounded_hourly_rate > 0:
            name = "funded"

        time_records.append(
            dict(
                name=name,
                list_name=f"{list_name} {name}",
                billable_status=record["billable_status"],
                rate=round(hourly_rate, 2) if rounded_hourly_rate > 0 else 0,
                value=round(record["value"] * 60 * 60 * 1000, 2),
                ts=record["record_date"] * 1000,
                summary=record["summary"],
                tag=job_type,
                task_id=record["parent_id"]
                if record["parent_type"] == "Task"
                else None,
                created_by_id=record["created_by_id"],
            )
        )

    time_records = sorted(time_records, key=lambda x: x["rate"])
    rates = list(set([0, *[tr["rate"] for tr in time_records]]))
    time_records = [
        {
            **tr,
            "list_name": f"{tr['list_name']} {rates.index(tr['rate'])}"
            if rates.index(tr["rate"]) > 1
            else tr["list_name"],
        }
        for tr in time_records
    ]

    time_records_with_rate = filter(lambda x: x["rate"] > 0, time_records)

    prepared_time_records = []
    for record in time_records:
        try:
            if record["name"] == 0 and len(list(time_records_with_rate)):
                closest = min(
                    time_records_with_rate, key=lambda x: abs(x["ts"] - record["ts"])
                )
                record["name"] = closest["name"]
                record["list_name"] = closest["list_name"]

            prepared_time_records.append(record)
        except:
            # At this point, we do nothing!
            pass
    return prepared_time_records


def import_ac_task(
    clickup: ClickUp,
    task_list_id: int,
    ac_task: dict,
    members: dict,
    job_types: dict,
    time_rate: int = -1,
) -> tuple:
    task_comment_map = {}

    if not is_task_importable(ac_task):
        return None, None

    single = ac_task["single"]
    name = single["name"]

    job_type_id = str(single["job_type_id"])
    rate = time_rate if time_rate >= 0 else job_types.get(job_type_id, 0)
    if rate < 1:
        rate = 0

    tags = get_task_tags(name)
    status = get_task_status(ac_task)

    rate_field_id = "83c64fc3-773b-4006-bc0d-ab26c930efbd"

    custom_fields = [
        # rate
        dict(id=rate_field_id, value=rate),
        # spend to date
        dict(id="908f88f1-677a-4ee9-a814-1c6d0fff1166", value=0),
    ]

    data = dict(
        markdown_description=html_to_markdown(single["body"]),
        assignees=[],
        tags=tags,
        status=status,
        priority=1 if single["is_important"] else None,
        due_date_time=False,
        time_estimate=single["estimate"] * 60 * 60 * 1000,
        start_date_time=False,
        custom_fields=custom_fields,
    )

    if member := get_assignee(members, single["assignee_id"], True):
        data["assignees"] = [member["user"]["id"]]

    if due_date := single["due_on"]:
        data["due_date"] = due_date * 1000

    if start_date := single["start_on"]:
        data["start_date"] = start_date * 1000

    token = None
    if member := members.get(single["created_by_id"]):
        token = member["token"]

    task = clickup.get_or_create_task(task_list_id, name, json.dumps(data), token)
    if name.lower() == "check project status":
        clickup.set_custom_field(task["id"], rate_field_id, rate)

    data = dict()

    if subscribers := ac_task["subscribers"]:
        followers = []
        for sub in subscribers:
            if member := members.get(sub):
                followers.append(member["user"]["id"])

        if followers:
            data["followers"] = dict(add=followers)

    task = clickup.update_task(task["id"], data)

    for subtask in ac_task["subtasks"]:
        data = dict(
            parent=task["id"],
            name=subtask["name"],
            status="Closed" if subtask["is_completed"] else status,
        )

        if member := get_assignee(members, subtask["assignee_id"], True):
            data["assignees"] = [member["user"]["id"]]

        token = None
        if member := members.get(subtask["created_by_id"]):
            token = member["token"]

        clickup.get_or_create_task(
            task_list_id, subtask["name"], json.dumps(data), token
        )

    for comment in ac_task["comments"]:
        token = None
        if member := members.get(comment["created_by_id"]):
            token = member["token"]

        text = comment["body_plain_text"]
        text = f"Originally posted by {comment['created_by_name']} on {get_date(comment['created_on'])} \n{text}"

        task_comment_map[comment["id"]] = comment["parent_id"]
        clickup.get_or_create_comment(task["id"], text, token)

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
        return ["_meta", "status"]

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


def get_assignee(members: dict, ac_user_id: int, reassign:bool = False) -> Optional[dict]:
    if ac_user_id == 0:
        return None

    # If we are importing a task, reassign FDP -> SF.
    # We only do this if we are assigning a task
    if reassign:
        if ac_user_id == 212:
            return members.get(264)

    if ac_user_id not in members:
        missing_id = f"ac_{ac_user_id}"
        logger.warning(
            f"User {ac_user_id}: {members[missing_id]['display_name']} not in ClickUp"
        )
        return members.get(36)

    return members.get(ac_user_id)

def get_project_mappings(mapping_csv:str = 'data/ac_projects.csv') -> dict:
    mappings = {}
    with open(mapping_csv, newline='') as f:
        cf = csv.reader(f)
        header = next(cf)

        for row in cf:
            mappings[row[0]] = {
                "name": row[1],
                "import_type": row[9],
                "clickup_template": row[10],
                "unbillable_list": row[11] if len(row) > 12 else ''
            }
    return mappings



def html_to_markdown(html: str) -> str:
    return markdownify(html, escape_codeblocks=True, heading_style="ATX")


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description = "Description for my parser")
    parser.add_argument("-n", "--noattachments", action='store_true', help = "Don't Import Attachments", required = False)
    parser.add_argument("-l", "--limit", help = "Limit projects to import (e.g. -l 2,3,4)", required = False, default = "")
    argument = parser.parse_args()

    if argument.noattachments:
        import_attachments = False
        print("Not importing attachments")

    if argument.limit:
        limit_projects = argument.limit.split(",")
        limit_projects_resume = limit_projects.copy()

        print("Importing these projects: {0}".format(limit_projects))
    else:
        limit_projects_resume = []
        path = "data"
        with open(os.path.join(path, "projects.json"), "r") as f:
            ac_projects = json.load(f)
            for project in ac_projects:
                limit_projects_resume.append(project["id"])
    
        with open(os.path.join(path, "archived_projects.json"), "r") as f:
            archived_projects = json.load(f)
            for project in archived_projects:
                limit_projects_resume.append(project["id"])

    with open("clickup_secrets.json.nogit", "r") as f:
        secrets = json.load(f)

    # Generate mapping
    project_mappings = get_project_mappings()

    clickup = ClickUp(
        secrets["team_id"], secrets["api_token_v1"], secrets["api_tokens_v2"]["default"]
    )

    spaces = import_ac_labels(clickup)

    members = get_members(clickup, tokens=secrets["api_tokens_v2"])

    folders, lists, docs, pages, tasks, comment_map = import_ac_projects(
        clickup, spaces, members
    )

    if import_attachments:
        attachments = import_ac_attachments(clickup, tasks, comment_map, folders)
