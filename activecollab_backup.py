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

#BACKUP_DIR = '/vol/kdldata/ActiveCollabBackup'
BACKUP_DIR = '../data'



# ############################################
# Stop editing here!
# ############################################

DAILY_DIR = 'daily'

FOLDER_NAME = time.strftime('%Y%m%d%H%M%S')

# Current working directory
CWD = os.path.join(BACKUP_DIR, DAILY_DIR, FOLDER_NAME)

def main():
    # Ensure folder structure
    create_dir(os.path.join(BACKUP_DIR, DAILY_DIR))

    daily()

# Run a daily backup
def daily():

    # Create our cwd
    create_dir(CWD)
    create_dir(os.path.join(CWD, 'projects'))
    create_dir(os.path.join(CWD, 'projects/archived'))

   # Get job types
    job_types = ac.get('job-types')
    save_file(job_types, 'job_types.json')

    # Get Expense Categories
    expense_categories = ac.get('expense-categories')
    save_file(expense_categories, 'expense_categories.json')

    # Get Categories
    categories = ac.get('projects/categories')
    save_file(categories, 'categories.json')

    # Get Labels
    labels = ac.get('projects/labels')
    save_file(labels, 'labels.json')

   # Get Task Labels
    task_labels = ac.get('labels/task-labels')
    save_file(task_labels, 'task_labels.json')



    # Get Companies
    companies = ac.get('companies')
    save_file(companies, 'companies.json')

    # Get Users
    users = ac.get('users')
    save_file(users, 'users.json')

    # Get Trash
    trash = ac.get('trash')
    save_file(trash, 'trash.json')

    # Get Invoices
    invoices = ac.get('invoices')
    save_file(invoices, 'invoices.json')

    # Get Projects
    projects = []
    project_page = []

    # Iterate over until we get an empty list...
    page = 1

    while page == 1 or not len(project_page) == 0:
        project_page = ac.get('projects?page={0}'.format(page))
        projects = projects + project_page
        page = page + 1

    save_file(projects, 'projects.json')

    for project in projects:
        pid = project['id']

        # Create our project tree
        project_dir = os.path.join(CWD, 'projects', str(pid))
        tasks_dir = os.path.join(project_dir, 'tasks')
        discussions_dir = os.path.join(project_dir, 'discussions')
        archived_tasks_dir = os.path.join(tasks_dir, 'archived')

        create_dir(project_dir)
        create_dir(tasks_dir)
        create_dir(discussions_dir)
        create_dir(archived_tasks_dir)

        # Get Project Expenses
        expenses = ac.get('projects/{0}/expenses'.format(pid))
        save_file(expenses, os.path.join(project_dir, 'expenses.json'))

        # Get time records
        time_records = ac.get('projects/{0}/time-records'.format(pid))
        save_file(time_records, os.path.join(project_dir, 'time-records.json'))

        # Get Project Notes
        notes = ac.get('projects/{0}/notes'.format(pid))
        save_file(notes, os.path.join(project_dir, 'notes.json'))

        # Get Project Tasks
        tasks = ac.get('projects/{0}/tasks'.format(pid))
        save_file(tasks, os.path.join(project_dir, 'tasks.json'))

 

        if len(tasks['tasks']):
            for task in tasks['tasks']:
                tid = task['id']
                task_json = ac.get('projects/{0}/tasks/{1}'.format(pid, tid))
                task_dir = os.path.join(tasks_dir, '{0}'.format(tid))
                create_dir(task_dir)
                save_file(task_json, os.path.join(task_dir, 'tasks.json'))

                if task['total_subtasks'] > 0:
                    subtask_json = ac.get('projects/{0}/tasks/{1}/subtasks'.format(pid, tid))
                    save_file(subtask_json, os.path.join(task_dir, 'subtasks.json'))


        # Get Archived Tasks
        tasks = []
        task_page = []

        # Iterate over until we get an empty list...
        page = 1
        while page == 1 or not len(task_page) == 0:
            task_page = ac.get('projects/{0}/tasks/archive?page={1}'.format(pid, page))
            tasks = tasks + task_page
            page = page + 1

        # Get Archived (complete) Tasks
        save_file(tasks, os.path.join(project_dir, 'archived-tasks.json'))

        if len(tasks):
            for task in tasks:
                tid = task['id']
                task_json = ac.get('projects/{0}/tasks/{1}'.format(pid, tid))
                task_dir = os.path.join(archived_tasks_dir, '{0}'.format(tid))
                create_dir(task_dir)
                save_file(task_json, os.path.join(task_dir, 'tasks.json'))

                if task['total_subtasks'] > 0:
                    subtask_json = ac.get('projects/{0}/tasks/{1}/subtasks'.format(pid, tid))
                    save_file(subtask_json, os.path.join(task_dir, 'subtasks.json'))


        
        # Get Project Discussions
        discussions = ac.get('projects/{0}/discussions'.format(pid))
        save_file(discussions, os.path.join(project_dir, 'discussions.json'))

        if len(discussions['discussions']):
            for discussion in discussions['discussions']:
                did = discussion['id']
                discussion = ac.get('projects/{0}/discussions/{1}'.format(pid, did))
                save_file(discussion, os.path.join(discussions_dir, '{0}.json'.format(did)))


    # Get Archived Projects
    archived_projects = []
    project_page = []

    # Iterate over until we get an empty list...
    page = 1
    while page == 1 or not len(project_page) == 0:
        project_page = ac.get('projects/archive?page={0}'.format(page))
        archived_projects = archived_projects + project_page
        page = page + 1

    save_file(archived_projects, 'archived_projects.json')

    for project in archived_projects:
        pid = project['id']

        # Create our project tree
        project_dir = os.path.join(CWD, 'projects/archived', str(pid))
        tasks_dir = os.path.join(project_dir, 'tasks')
        discussions_dir = os.path.join(project_dir, 'discussions')
        archived_tasks_dir = os.path.join(tasks_dir, 'archived')

        create_dir(project_dir)
        create_dir(tasks_dir)
        create_dir(discussions_dir)
        create_dir(archived_tasks_dir)

        # Get Project Expenses
        expenses = ac.get('projects/{0}/expenses'.format(pid))
        save_file(expenses, os.path.join(project_dir, 'expenses.json'))

        # Get time records
        time_records = ac.get('projects/{0}/time-records'.format(pid))
        save_file(time_records, os.path.join(project_dir, 'time-records.json'))

        # Get Project Notes
        notes = ac.get('projects/{0}/notes'.format(pid))
        save_file(notes, os.path.join(project_dir, 'notes.json'))

        # Get Project JSON (for hourly rates)
        tasks = ac.get('projects/{0}'.format(pid))
        save_file(tasks, os.path.join(project_dir, 'project.json'))

        if len(tasks['tasks']):
            for task in tasks['tasks']:
                tid = task['id']
                task_json = ac.get('projects/{0}/tasks/{1}'.format(pid, tid))
                save_file(task_json, os.path.join(tasks_dir, '{0}.json'.format(tid)))

         # Get Archived (complete) Tasks
        tasks = []
        task_page = []

        # Iterate over until we get an empty list...
        page = 1
        while page == 1 or not len(task_page) == 0:
            task_page = ac.get('projects/{0}/tasks/archive?page={1}'.format(pid, page))
            tasks = tasks + task_page
            page = page + 1

        save_file(tasks, os.path.join(project_dir, 'archived-tasks.json'))

        if len(tasks):
            for task in tasks:
                tid = task['id']
                task_json = ac.get('projects/{0}/tasks/{1}'.format(pid, tid))
                save_file(task_json, os.path.join(archived_tasks_dir, '{0}.json'.format(tid)))

        
        # Get Project Discussions
        discussions = ac.get('projects/{0}/discussions'.format(pid))
        save_file(discussions, os.path.join(project_dir, 'discussions.json'))

        if len(discussions['discussions']):
            for discussion in discussions['discussions']:
                did = discussion['id']
                discussion = ac.get('projects/{0}/discussions/{1}'.format(pid, did))
                save_file(discussion, os.path.join(discussions_dir, '{0}.json'.format(did)))

# Creates a directory if it doesn't exist
def create_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)

# Saves a JSON file to the current working directory
def save_file(jsonfile, filename):
    with open(os.path.join(CWD, filename), 'w') as outfile:
        simplejson.dump(jsonfile, outfile)

if __name__ == '__main__':
    main()
