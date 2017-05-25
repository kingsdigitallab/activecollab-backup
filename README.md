# activecollab-backup
Script for backing up data from an ActiveCollab cloud instance.

## Installation
* Create a virtual environment `env` in the directory (this will be ignored by git): `virtualenv env`
* Install requirements into the virtual environment `source env/bin/activate && pip install -r requirements.txt && deactivate`
* Add `activecollab_backup.sh` to crontab to run on a daily basis

## Authentication
Before running, ensure `ac_token` is set in `ac_secrets.json.nogit`

## activecollab_backup.py
This is a python script which grabs all relevent data from activecollab, and saves it in the folder specified in the script.

You should set the following variables:
* `BACKUP_DIR`: Absolute path to the backup directory
* `KEEP_DAILY`: How many daily backups to keep
* `KEEP_WEEKLY`: How many weekly backups to keep
* `WEEKLY_DOW`: Day of week to save weekly snapshot
* `MONTHLY_DOM`: Day of month to save monthly snapshot
Files will be saved into a subfolder of `BACKUP_DIR`, in the format `YYYYMMDDHHMM`.

Note: *All* monthly backups are kept - there is no rotation for monthly backups.

## activecollab_backup.sh
This is a helper script which:

* Activates the virtual environment
* Runs the python script
* Deactives the virtual environment
