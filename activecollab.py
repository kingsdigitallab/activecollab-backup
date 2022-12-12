import requests
import simplejson

ac_secrets = {}

with open('ac_secrets.json.nogit') as f:
#with open('/vol/linux/bin/activecollab-backup/ac_secrets.json.nogit') as f:
    ac_secrets = simplejson.loads(f.read())


AC_BASE_URL = 'https://app.activecollab.com/148987/api/v1/'
AC_TOKEN = ac_secrets['ac_token']
AC_HEADERS = {
    'X-Angie-AuthApiToken': AC_TOKEN,
    'Content-Type': 'application/json; charset=utf-8'
}

def get(api_path, params=None):
    r = requests.get('{0}{1}'.format(
        AC_BASE_URL, api_path), params=simplejson.dumps(params),
        headers=AC_HEADERS)
    try:
        return r.json()
    except:
        return None

def get_nojson(api_path, params=None):
    r = requests.get('{0}{1}'.format(
        AC_BASE_URL, api_path), params=simplejson.dumps(params),
        headers=AC_HEADERS)
    return r

def post(api_path, params=None):
    r = requests.post('{0}{1}'.format(
        AC_BASE_URL, api_path), data=simplejson.dumps(params),
        headers=AC_HEADERS)

    return r.json()


def put(api_path, params=None):
    r = requests.put('{0}{1}'.format(AC_BASE_URL, api_path),
                     data=simplejson.dumps(params), headers=AC_HEADERS)
    return r.json()


def upload(files):
    r = requests.post('{0}upload-files'.format(
        AC_BASE_URL), files=files, headers=AC_HEADERS_UPLOAD)
    return r.json()
