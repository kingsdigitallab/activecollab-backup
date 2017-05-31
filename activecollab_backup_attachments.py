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

BACKUP_DIR = '/vol/kdldata/ActiveCollabBackup'
#BACKUP_DIR = '/Users/brian/Downloads'

# ############################################
# Stop editing here!
# ############################################

ATTACH_DIR = 'attachments'

# Current working directory
CWD = os.path.join(BACKUP_DIR, ATTACH_DIR)

def main():
    download_attachments()


# Run a daily backup
def download_attachments():

    # Create our cwd
    create_dir(CWD)

    # Get Projects - we're going to bundle attachments and 
    projects = []
    project_page = []

    # Iterate over until we get an empty list...
    page = 1

    while page == 1 or not len(project_page) == 0:
        project_page = ac.get('projects?page={0}'.format(page))
        projects = projects + project_page
        page = page + 1

    # Get Archived Projects
    # Iterate over until we get an empty list...
    page = 1
    while page == 1 or not len(project_page) == 0:
        project_page = ac.get('projects/archive?page={0}'.format(page))
        projects = projects + project_page
        page = page + 1

    for project in projects:
        pid = project['id']

        # Create our project tree
        attachment_dir = os.path.join(CWD, str(pid))

        create_dir(attachment_dir)
    

        # Get Project Files
        files = []
        file_page = []

        # Iterate over until we get an empty list...
        page = 1
        while page == 1 or not len(file_page) == 0:
            file_page = ac.get('projects/{0}/files?page={1}'.format(pid, page))['files']
            files = files + file_page
            page = page + 1

        # Save JSON, so we can link attachment ids to names...
        save_file(files, '{0}.json'.format(pid))

        for f in files:
            fid = f['id']
            fclass = f['class']
            furl = f['download_url']

            # Check if it's google drive, if it is, we aren't bothered.
            if not fclass == 'GoogleDriveFile':
                fpath = os.path.join(attachment_dir, str(fid))

                # Does it already exist?
                if not os.path.isfile(fpath):
                    r = requests.get(furl)
                    with open(fpath, 'wb') as file:
                        file.write(r.content)


# Creates a directory if it doesn't exist
def create_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


# Saves a JSON file to the current working directory
def save_file(jsonfile, filename):
    with open(os.path.join(CWD, filename), 'wb') as outfile:
        simplejson.dump(jsonfile, outfile)

if __name__ == '__main__':
    main()
