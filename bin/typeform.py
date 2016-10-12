#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Installation (Python 3)
-----------------------

    virtualenv -p python3 ~/virtenvs/devconfcz/
    source ~/virtenvs/devconfcz/bin/activate
    pip install hyde requests click pandas df2gspread


Example Config
--------------
    cat <<EOT >> ~/.config/typeform/config.json
    {
        "url": "https://api.typeform.com/v1/form/SB4LW3",
        "params": {
            "key": "HIDDEN_KEY",
            "completed": "true"
        }
    }

Usage
-----
    ./typeform.py count [sessions]
    ./typeform.py count speakers


EOT

"""

from collections import defaultdict, Counter
import datetime
import json
import os
import re
import requests
import shutil
import subprocess
import time

import click  # http://click.pocoo.org/6/
from df2gspread import df2gspread as d2g
import pandas as pd


## LOAD CONFIG FILE ##

base_path = os.path.expanduser("~/.config/typeform/")
config_file = os.path.join(base_path, "config.json")
config = json.load(open(config_file))
url = config['url']
params = config['params']


## Set-Up some CONSTANTS
QUESTION_ALIAS = {
    'Speaker Agreement': 'agreement',
    'Session Title': 'title',
    'Session Type': 'type',
    'Session Theme': 'theme',
    'Session Difficulty': 'difficulty',
    'Session Abstract / Description': 'abstract',
    'What\'s the primary speakers name?': 'name',
    'Where is the primary speaker traveling from?': 'country',
    'Primary speakers background / bio?': 'bio',
    'Primary Speaker\'s Organizational Affiliation': 'org',
    'Primary Speakers wearables size?': 'size',
    'Primary speaker\'s email address?': 'email',
    'Link to primary speaker\'s \xa0Avatar / Profile Pic': 'avatar',
    'Primary Speaker\'s Twitter handle?': 'twitter',
    'Secondary Speaker Info': 'secondary',
}

SPEAKER_FIELDS = ['name', 'country', 'bio', 'org', 'size',
                  'email', 'avatar', 'twitter', 'secondary']

SESSION_FIELDS = ['submitted', 'title', 'type', 'theme', 'difficulty',
                  'abstract']


## Shared Functions

def _clean_twitter(handle):
    handle = str(handle or "")  # makes sure we're working with a string
    handle = handle.lstrip('@')  # clear any existing @ if present
    handle = handle.split('/')[-1]  # grab handle only in case of https://...
    # assume 1c handles are invalid
    handle = handle if len(handle) > 1 else ""
    return handle


def _get_data(url, params):
    ## Set-up Working Variables ##
    r = requests.get(url, params=params)
    results = r.json()

    # parse out the question labels
    questions = dict((x['id'], x['question']) for x in results['questions'])
    # parse out all the responses
    responses = results['responses']

    # Prepare buckets for speakers and sessions separately
    proposals = []

    for response in responses:
        # These are the actual form responses
        answers = response['answers']
        # Grab the date the form was submitted
        dt_str = response['metadata']['date_submit']
        dt = datetime.datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
        _id = (
            response['metadata']['network_id'] + '+' + dt_str).replace(' ', '')

        # Save the submission date
        proposal = {'_id': _id, 'submitted': dt}
        # Gonna aggregate multiple themes into a single list
        proposal['theme'] = []

        for field, value in answers.items():
            value = value.strip()
            # Grab the actual (though unreadable) form label id
            _field = questions[field]
            # Swap it with the simplified field alias for dict keys
            alias = QUESTION_ALIAS[_field]

            if alias == 'theme':
                proposal[alias].append(value)
            elif alias == 'twitter':
                value = _clean_twitter(value)
                proposal[alias] = value
            else:
                proposal[alias] = value

        else:
            proposal['theme'] = '; '.join(sorted(proposal['theme']))
            proposals.append(proposal)

    # Reverse Sort by date submitted
    proposals = pd.DataFrame(proposals).fillna("UNKNOWN")
    # reorder the colomns
    proposals = proposals[SESSION_FIELDS + SPEAKER_FIELDS]
    return proposals


def _convert_datetime(dt):
    dt_format = '%Y-%m-%d'

    if dt == 'today':
        dt = str(datetime.date.today())
    elif dt == 'yesterday':
        dt = str(
            datetime.date.fromordinal(datetime.date.today().toordinal() - 1))

    epoch = time.mktime(time.strptime(dt, dt_format))

    return int(epoch)


def _split_resources(proposals):
    # split out proposals into speakers and sessions
    sessions = proposals[SESSION_FIELDS]
    speakers = proposals[SPEAKER_FIELDS]
    return sessions, speakers


def _download(url, path):
    from io import open as iopen

    try:
        i = requests.get(url)
        if i.status_code == requests.codes.ok:
            with iopen(path, 'wb') as file:
                file.write(i.content)

        cmd = "file {}".format(path)
        process = subprocess.Popen(cmd.split(), stdout=subprocess.PIPE)
        output, error = process.communicate()

        output = str(output)
        if re.search(r'PNG image', output):
            ext = '.png'
        elif re.search(r'JPEG image', output):
            ext = '.jpg'
        else:
            raise ValueError("Invalid image ({})".format(output))
        _path = path + ext
        os.rename(path, _path)
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        print("ERROR: {})\n".format(e))
        url = "http://placehold.it/300x300"
        path = path.split('.')[:-1] + '.png'
        _download(url, path)


def _diff_submissions(path, wks_name, proposals):
    # access credentials
    credentials = d2g.get_credentials()
    # auth for gspread
    gc = d2g.gspread.authorize(credentials)

    try:
        # if gfile is file_id
        gc.open_by_key(path)
        gfile_id = path
    except Exception:
        # else look for file_id in drive
        gfile_id = get_file_id(credentials, path, write_access=True)

    wks = d2g.get_worksheet(gc, gfile_id, wks_name, write_access=True)
    rows = wks.get_all_values()
    rows_k = len(rows)  # includes the header row already
    if rows_k > 0:
        columns = rows.pop(0)  # header
        df = pd.DataFrame(rows, columns=columns)
        start_cell = 'A' + str(rows_k + 1)
        col_names = False
        new_proposals = proposals[len(df.index):]
        return start_cell, col_names, new_proposals
    else:
        # new sheet, nothing to do
        start_cell = 'A1'
        col_names = True
        return start_cell, col_names, proposals


## CLI Set-up ##

@click.group()
@click.option('--since', default=None, help='Filter by submission date')
@click.pass_context
def cli(ctx, since):
    """Download and prepare the form responses for further processing"""

    # Apply Filters
    if since:
        # convert to UNIX timestamp
        since = _convert_datetime(since)
        params['since'] = since

    proposals = _get_data(url, params)
    sessions, speakers = _split_resources(proposals)

    ctx.obj['proposals'] = proposals
    ctx.obj['sessions'] = sessions
    ctx.obj['speakers'] = speakers


@cli.command()
@click.option('--csv', default=False, is_flag=True)
@click.option('--upload', default=False, is_flag=True,
              help='Save remotely to gspreadsheet?')
@click.option('--html', default=False, is_flag=True)
@click.option('--path', help='Output directory')
@click.pass_obj
def save(obj, csv, upload, html, path):
    proposals = obj['proposals']
    if not (csv or upload or html):
        csv = True

    if csv:
        path = path or './'
        path = os.path.join(path, "devconfcz_proposals.csv")
        f = open(path, 'w')
        proposals.to_csv(f)

    if upload:
        path = path or 'devconfcz_proposals'

        wks = 'Submissions MASTER'  # "update" the existing sheet

        # grab only the items we don't already have so we
        # can APPEND them to the sheet rather than rewritting
        # the whole sheet
        start_cell, col_names, proposals = _diff_submissions(path, wks,
                                                             proposals)
        if not proposals.empty:
            d2g.upload(proposals, path, wks, start_cell=start_cell,
                       clean=False, col_names=col_names)
        else:
            print("No new proposals to upload... QUITTING!")

    if html:
        print(proposals.style.render())


@cli.command()
@click.argument('resource', default='sessions',
                type=click.Choice(['sessions', 'speakers', 'proposals']))
@click.pass_obj
def count(obj, resource):
    resources = obj[resource]
    click.echo(len(resources))


@cli.command()
@click.option('--path', help='Output Path')
@click.pass_obj
def avatars(obj, path):
    path = os.path.expanduser(path or "/tmp/avatars")

    if not os.path.exists(path):
        os.makedirs(path)

    for row in obj['speakers'][['email', 'avatar']].itertuples():
        email, url = row.email.replace('@', '__at__'), row.avatar
        print("Loading {} ".format(url), end="", flush=True)  # NOQA
        filename = email
        _path = os.path.join(path, filename)
        print("as {} ".format(filename))
        _download(url, _path)


@cli.command()
@click.argument('cmd', default='theme',
                type=click.Choice(['theme', 'difficulty', 'country',
                                   'org', 'name']))
@click.pass_obj
def report(obj, cmd):
    proposals = obj['proposals']

    stuff = []
    if cmd == 'theme':
        _types = proposals.theme
        _types.apply(lambda x: stuff.extend(x.split('; ')))
    elif cmd in ['difficulty', 'country', 'org', 'name']:
        _types = proposals[cmd]
        _types.apply(lambda x: stuff.append(x))
    else:
        raise ValueError('Invalid command: {}'.format(cmd))

    stuff = dict(Counter(stuff))

    for k, v in sorted(stuff.items(), key=lambda x: x[1], reverse=True):
        print("{:<40}: {}".format(k[:40], v))


if __name__ == '__main__':
    cli(obj={})
