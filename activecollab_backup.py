#!/usr/bin/env python

import os
import time
import datetime
import requests
import simplejson
import shutil
import activecollab as ac

from glob import glob

# ############################################
# Set your variables here:
# ############################################

BACKUP_DIR = "/vol/kdldata/ActiveCollabBackup"

KEEP_DAILY = 7
KEEP_WEEKLY = 4

WEEKLY_DOW = 6 # Day of week (Default 6 = Sunday)
MONTHLY_DOM = 1 # Day of the month (Default 1st)

# ############################################
# Stop editing here!
# ############################################

DAILY_DIR = "daily"
WEEKLY_DIR = "weekly"
MONTHLY_DIR = "monthly"

FOLDER_NAME = time.strftime("%Y%m%d%H%M%S")

# Current working directory
CWD = os.path.join(BACKUP_DIR, DAILY_DIR, FOLDER_NAME)

def main():
    # Ensure folder structure
    create_dir(os.path.join(BACKUP_DIR, DAILY_DIR))
    create_dir(os.path.join(BACKUP_DIR, WEEKLY_DIR))
    create_dir(os.path.join(BACKUP_DIR, MONTHLY_DIR))

    daily()
    weekly()
    monthly()

# Run a daily backup
def daily():

    # Create our cwd
    create_dir(CWD)
    create_dir(os.path.join(CWD, "projects"))
    create_dir(os.path.join(CWD, "projects/archived"))

    # Get Categories
    categories = ac.get("projects/categories")
    save_file(categories, "categories.json")

    # Get Labels
    labels = ac.get("projects/labels")
    save_file(labels, "labels.json")

    # Get Companies
    companies = ac.get("companies")
    save_file(companies, "companies.json")

    # Get Users
    users = ac.get("users")
    save_file(users, "users.json")

    # Get Trash
    trash = ac.get("trash")
    save_file(trash, "trash.json")

    # Get Invoices
    invoices = ac.get("invoices")
    save_file(invoices, "invoices.json")

    # Get Projects
    projects = ac.get("projects")
    save_file(projects, "projects.json")

    for project in projects:
        pid = project['id']

        # Create our project tree
        project_dir = os.path.join(CWD, "projects", str(pid))
        tasks_dir = os.path.join(project_dir, "tasks")
        discussions_dir = os.path.join(project_dir, "discussions")
        archived_tasks_dir = os.path.join(task_dir, "archived")

        create_dir(project_dir)
        create_dir(tasks_dir)
        create_dir(discussions_dir)
        create_dir(archived_tasks_dir)

        # Get Project Notes
        notes = ac.get("projects/{0}/notes".format(pid))
        save_file(notes, os.path.join(project_dir, "notes.json"))

        # Get Project Tasks
        tasks = ac.get("projects/{0}/tasks".format(pid))
        save_file(tasks, os.path.join(project_dir, "tasks.json"))

        if len(tasks['tasks']):
            for task in tasks['tasks']:
                tid = task['id']
                task_json = ac.get("projects/{0}/tasks/{1}".format(pid, tid))
                save_file(task_json, os.path.join(tasks_dir, "{0}.json".format(tid)))

        # Get Archived (complete) Tasks
        tasks = ac.get("projects/{0}/tasks/archive".format(pid))
        save_file(tasks, os.path.join(project_dir, "archived-tasks.json"))

        if len(tasks):
            for task in tasks:
                tid = task['id']
                task_json = ac.get("projects/{0}/tasks/{1}".format(pid, tid))
                save_file(task_json, os.path.join(archived_tasks_dir, "{0}.json".format(tid)))

        
        # Get Project Discussions
        discussions = ac.get("projects/{0}/discussions".format(pid))
        save_file(discussions, os.path.join(project_dir, "discussions.json"))

        if len(discussions['discussions']):
            for discussion in discussions['discussions']:
                did = discussion['id']
                discussion = ac.get("projects/{0}/discussions/{1}".format(pid, did))
                save_file(discussion, os.path.join(discussions_dir, "{0}.json".format(did)))


    # Get Archived Projects
    archived_projects = ac.get("projects/archive")
    save_file(archived_projects, "archived_projects.json")

    for project in archived_projects:
        pid = project['id']

        # Create our project tree
        project_dir = os.path.join(CWD, "projects/archived", str(pid))
        tasks_dir = os.path.join(project_dir, "tasks")
        discussions_dir = os.path.join(project_dir, "discussions")
        archived_tasks_dir = os.path.join(tasks_dir, "archived")

        create_dir(project_dir)
        create_dir(tasks_dir)
        create_dir(discussions_dir)
        create_dir(archived_tasks_dir)

        # Get Project Notes
        notes = ac.get("projects/{0}/notes".format(pid))
        save_file(notes, os.path.join(project_dir, "notes.json"))

        # Get Project Tasks
        tasks = ac.get("projects/{0}/tasks".format(pid))
        save_file(tasks, os.path.join(project_dir, "tasks.json"))

        if len(tasks['tasks']):
            for task in tasks['tasks']:
                tid = task['id']
                task_json = ac.get("projects/{0}/tasks/{1}".format(pid, tid))
                save_file(task_json, os.path.join(tasks_dir, "{0}.json".format(tid)))

         # Get Archived (complete) Tasks
        tasks = ac.get("projects/{0}/tasks/archive".format(pid))
        save_file(tasks, os.path.join(project_dir, "archived-tasks.json"))

        if len(tasks):
            for task in tasks:
                tid = task['id']
                task_json = ac.get("projects/{0}/tasks/{1}".format(pid, tid))
                save_file(task_json, os.path.join(archived_tasks_dir, "{0}.json".format(tid)))

        
        # Get Project Discussions
        discussions = ac.get("projects/{0}/discussions".format(pid))
        save_file(discussions, os.path.join(project_dir, "discussions.json"))

        if len(discussions['discussions']):
            for discussion in discussions['discussions']:
                did = discussion['id']
                discussion = ac.get("projects/{0}/discussions/{1}".format(pid, did))
                save_file(discussion, os.path.join(discussions_dir, "{0}.json".format(did)))

    # Rotate!
    rotate(DAILY_DIR, KEEP_DAILY)

# Organise weekly backups
def weekly():
    if datetime.datetime.today().weekday() == WEEKLY_DOW:
        shutil.copytree(CWD, os.path.join(BACKUP_DIR, WEEKLY_DIR, FOLDER_NAME))

    # Rotate!
    rotate(WEEKLY_DIR, KEEP_WEEKLY)

# Organise monthly backups
def monthly():
    if datetime.datetime.today().day == MONTHLY_DOM:
        shutil.copytree(CWD, os.path.join(BACKUP_DIR, MONTHLY_DIR, FOLDER_NAME))

# Creates a directory if it doesn't exist
def create_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Quick method for rotating backups
def rotate(folder, keep):
    scan_path = os.path.join(BACKUP_DIR, folder, "*")
    # Being safe in case of implementation differences
    if not scan_path.endswith("/"):
        scan_path = "{0}/".format(scan_path)
    folders = sorted(glob(scan_path))
    for folder in folders[:-keep]:
        shutil.rmtree(folder)

# Saves a JSON file to the current working directory
def save_file(jsonfile, filename):
    with open(os.path.join(CWD, filename), "wb") as outfile:
        simplejson.dump(jsonfile, outfile)

if __name__ == '__main__':
    main()
