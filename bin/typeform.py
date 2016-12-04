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

BASE_PATH = os.path.expanduser("~/.config/typeform/")
CONFIG_FILE = os.path.join(BASE_PATH, "config.json")
config = json.load(open(CONFIG_FILE))
url = config['url']
params = config['params']

LABEL_MAP_FILE = os.path.join(BASE_PATH, 'label_map.json')
try:
    LABEL_MAP = json.load(open(LABEL_MAP_FILE))
except Exception:
    LABEL_MAP = {}

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

ALL_FIELDS = SPEAKER_FIELDS + SESSION_FIELDS


## Shared Functions

def _normalize_value(key, value):
    return LABEL_MAP.get(key, {}).get(value, value)


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
                proposal[alias] = _normalize_value(alias, value)

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
    try:
        columns = rows.pop(0)  # header
        df = pd.DataFrame(rows, columns=columns)
        df = df.drop(['', 'COMMENTS', 'VOTES', 'PROPOSED TRACK(S)'], axis=1)
        df = df[df['title'] != '']  # filter out empty rows

        rows_k = len(df)
        start_cell = 'A' + str(rows_k + 2)

        col_names = False
        new_proposals = proposals[len(df.index):]
        return start_cell, col_names, new_proposals
    except Exception:
        # new sheet, nothing to do
        start_cell = 'A1'
        col_names = True
        return start_cell, col_names, proposals


def _get_type(_type):
    try:
        return _type.split(' ')[0]
    except ValueError:
        # we have some custom type, ie "meetup"... assume  40 minute
        return 'UNKNOWN'


def _get_duration(_type):
    try:
        return int(_type.split(' ')[-1].split('+')[0].rstrip('m'))
    except ValueError:
        # we have some custom type, ie "meetup"... assume  40 minute
        return 'UNKNOWN'


def _get_gspread(path, wks_name):
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
        gfile_id = get_file_id(credentials, path, write_access=False)

    wks = d2g.get_worksheet(gc, gfile_id, wks_name, write_access=False)
    rows = wks.get_all_values()

    columns = rows.pop(0)  # header
    columns = [x.strip() for x in columns]
    #columns = [QUESTION_ALIAS[x.strip()] for x in columns]
    df = pd.DataFrame(rows, columns=columns)
    #df = df[df['timestamp'] != '']  # filter out empty rows

    #proposals = pd.DataFrame(proposals).fillna("UNKNOWN")
    # reorder the colomns
    #df = df[SESSION_FIELDS + SPEAKER_FIELDS]

    return df


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

    # MOVE TO _get_data... and call get_data in
    # the cli funs that need it
    # FIXME: This should run only when needed
    #proposals = _get_data(url, params)
    #sessions, speakers = _split_resources(proposals)

    #ctx.obj['proposals'] = proposals
    #ctx.obj['sessions'] = sessions
    #ctx.obj['speakers'] = speakers


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
                                   'org', 'name', 'type', 'title']))
@click.option('--sort', default=1, help="Sort key")
@click.pass_obj
def report(obj, cmd, sort):
    proposals = obj['proposals']

    stuff = []
    if cmd == 'theme':
        _types = proposals.theme
        _types.apply(lambda x: stuff.extend(x.split('; ')))
    elif cmd in ['difficulty', 'country', 'org', 'name', 'type', 'title']:
        _types = proposals[cmd]
        _types.apply(lambda x: stuff.append(x))
    else:
        raise ValueError('Invalid command: {}'.format(cmd))

    stuff = dict(Counter(stuff))

    for k, v in sorted(stuff.items(), key=lambda x: x[sort], reverse=True):
        print("{:<40}: {}".format(k[:40], v))

    if cmd == 'type':
        duration = 0
        for value in proposals['type']:
            duration += _get_duration(value)
        else:
            duration = int(duration / 60)
        print("Total duration: ~{} hours".format(duration))


@cli.command()
@click.argument('column', type=click.Choice(ALL_FIELDS))
@click.argument('query', nargs=-1)
@click.pass_obj
def search(obj, column, query):
    proposals = obj['proposals']

    # slup all the query args and create a single spaced string from it
    query = ' '.join(query)

    result = proposals[proposals[column].str.contains(query, na=False)]

    print(result[['name', 'title']])


import httplib2
import os
import oauth2client
from oauth2client import client, tools
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apiclient import errors, discovery

SCOPES = 'https://www.googleapis.com/auth/gmail.send'
CLIENT_SECRET_FILE = '/home/cward/Downloads/client_secret.json'
APPLICATION_NAME = 'Gmail API Python Send Email'

def get_credentials():
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir, 'gmail-python-email-send.json')
    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        credentials = tools.run_flow(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def SendMessage(sender, to, subject, msgHtml, msgPlain):
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    message1 = CreateMessage(sender, to, subject, msgHtml, msgPlain)
    SendMessageInternal(service, "me", message1)

def SendMessageInternal(service, user_id, message):
    try:
        message = (service.users().messages().send(userId=user_id, body=message).execute())
        print('Message Id: %s' % message['id'])
        return message
    except errors.HttpError as error:
        print('An error occurred: %s' % error)

def CreateMessage(sender, to, subject, msgHtml, msgPlain):
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = sender
    msg['To'] = to
    msg.attach(MIMEText(msgPlain, 'plain'))
    msg.attach(MIMEText(msgHtml, 'html'))
    raw = base64.urlsafe_b64encode(msg.as_bytes())
    raw = raw.decode()
    body = {'raw': raw}
    return body


@cli.command()
@click.pass_obj
def email(obj):
    speakers_db = pd.read_csv(
        '/home/cward/Downloads/DevConf.cz - MASTER db - speakers.csv')
    submissions_db = pd.read_csv(
        '/home/cward/Downloads/DevConf.cz - MASTER db - submissions.csv')
    sched = pd.read_csv('/home/cward/Downloads/DevConf.cz 2017 - Program Draft - All Sessions.csv')
    cfp_db = pd.read_csv('/home/cward/Downloads/Devconf.cz CfP Submissions - SOURCE - CLEAN Talks MASTER.csv')

    split_speakers = lambda x: [y.strip() for y in x.split(';')]
    # make the list of speakers a list of speakers
    sched['speakers'] = sched.speakers.map(split_speakers)

    _sess_template = '''
Title: {}
Type:  {}
Track: {}
Difficulty: {}
Duration (inc. Q&A): {} minutes

Speakers
========
'''

    _spkr_template = '''
Name:    {}
Email:   {}
Country: {}
Org:     {}
Shirt Size: {}
Twitter: {}
Avatar:  {}
Bio:
{}

'''

    print('ACCEPTED' + '*' * 79)
    # Get a dict of all accepted speaker ids reverse linked to session ids
    accepted = set()
    speaker_sessions = defaultdict(list)
    for row in sched.iterrows():
        row = row[1].to_dict()
        accepted.add(int(row['session_id']))
        speakers = row['speakers']
        # gather all the speaker details for the given speakers in each session
        speaker_details = []
        # first, gather all the speaker details for all speakers in the session
        for spkr in speakers:
            spkr = speakers_db[speakers_db.email == spkr].T.to_dict()
            if not spkr:
                continue
            spkr = spkr.popitem()[1]
            speaker_details.append(spkr)

        # then, combine those speaker details with the session details
        for spkr in speakers:
            speaker_sessions[spkr].append((row, speaker_details))

    x = 1
    y = len(speaker_sessions)
    for speaker, data in speaker_sessions.items():
        if speaker == 'shadowman': continue

        all_sessions = ''
        for _sess, _spkrs in data:
            title = _sess['title']
            _type = _sess['type']
            level = submissions_db[submissions_db['id'] == _sess['session_id']].difficulty.values[0]
            #import ipdb; ipdb.set_trace()
            track = _sess['track']
            _start = _sess['session_duration'].split(':')[1]
            _qa = _sess['session_qa'].split(':')[1]
            duration = int(_start) + int(_qa)
            _sess_str = _sess_template.format(
                title, _type, track, level, duration)
            _sess_spkrs_str = ''
            for _s in _spkrs:
                name = _s['name']
                email = _s['email']
                country = _s['country']
                org = _s['org']
                size = _s['size']
                twitter = str(_s['twitter']) if _s['twitter'] else ''
                twitter = '' if twitter == 'nan' else twitter
                avatar = _s['avatar']
                bio = _s['bio']
                _spkr = _spkr_template.format(name, email, country, org, size,
                                              twitter, avatar, bio)
                _sess_spkrs_str += _spkr
            all_sessions += _sess_str + _sess_spkrs_str

        body = email_accept.format(all_sessions)
        #to = "cward@redhat.com"
        to = speaker
        sender = "info@devconf.cz"
        subject = "[{}] DevConf.cz 2017 - Submission(s) ACCEPTED"
        subject = subject.format(speaker)
        msgHtml = body.replace('\n', '<br>')
        msgPlain = body
        print('Sending {} of {} [{}]'.format(x, y, speaker))
        x += 1
        # confirm before sending
        SendMessage(sender, to, subject, msgHtml, msgPlain)
        time.sleep(.1)
        #print(body)

    print('REJECTED' + '*' * 79)
    # now send rejection letters
    all_submissions = set([int(x) for x in cfp_db.id.values])
    rejected = defaultdict(list)
    for i in all_submissions:
        spkr = cfp_db[cfp_db.id == i].email.values[0]
        if i not in accepted:
            rejected[spkr].append(i)

    x = 1
    y = len(rejected)
    for spkr, session_ids in rejected.items():
        body = 'Rejected submission titles\n==========================\n\n'
        for i in session_ids:
            submission = cfp_db[cfp_db['id'] == i]
            title = submission.title.values[0]
            body += ' "{}" \n'.format(title)

        body = email_reject.format(body)
        to = spkr
        #to = "cward@redhat.com"
        sender = "info@devconf.cz"
        subject = "DevConf.cz 2017 - Submission(s) REJECTED [{}]"
        subject = subject.format(spkr)
        msgHtml = body.replace('\n', '<br>')
        msgPlain = body
        print('{} of {} [{}]'.format(x, y, spkr))
        x += 1
        SendMessage(sender, to, subject, msgHtml, msgPlain)
        time.sleep(.1)
        #print(body)

        #import ipdb; ipdb.set_trace()

email_reject = '''

Hi! I'm writing you to let you know that unfortunately we were not able
to squeeze the following session(s) that you submitted to DevConf.cz 2017
CfP into the event program this year. :(

{}

If anything changes and a slot frees up, we will let you know!

Note, if you submitted multiple copies of the same abstract it is possible
you might also receive a separate acceptance email confirmation. If you
do, congrats! The acceptance confirmation overrides this rejection confirmation.


This year all attendees must register for a FREE DevConf.cz ticket. It's quick
and easy. So, if you plan to attend DevConf.cz, here's the link for to register.

  http://bit.ly/devconf-cz-2017-registration


If you think there has been a mistake, have any other requests, questions or
concerns just let us know with a quick reply to this mail.


-- Chris and the rest of the DevConf.cz 2017 organizing team --


Email us at: info@devconf.cz

Subscribe to our newsletter for important event updates!
 * https://tinyletter.com/devconf_cz

Stop by during the event to say HELLO WORLD on Telegram:
 * https://telegram.me/joinchat/B1He_UEkuB4fBfY1cKCXRw

Follow us and what other's are tweeting about the event!
 * https://twitter.com/devconf_cz
 * hashtags: #devconf_cz #DEFINEfuture


'''

email_accept = '''
Nice work! Your submission(s) were accepted to DevConf.cz 2017 (see below).
This email contains important information about how to proceed from here. Read
carefully!  More info can also be found at devconf.cz.

Please confirm that you have received this mail and that you expect to speak
at DevConf.cz. If you believe there has been a mistake or for whatever reason
you can no longer participate in the event, let us know! Same goes if you have
any special requests or needs for your session / talk / workshop.

*** Confirm by December 16th or we will start looking for a replacement! ***

Finally, the extact day and time your session your session is scheduled for
will be announced in a separate email. Stay tuned!

You can reach us at info@devconf.cz

Sessions
--------
{}


Session Errata
--------------
All the information related to your submission and related speakers is included
above.

PLEASE NOTE: It is possible that your talk duration has been modified. If you
disagree with this change or believe there is some other mistake or if there
are any other changes you would like to make to your submission reply to this
email with the changes before Dec. 31st!


Registration
------------

This year all speakers and attendees must register to attend DevConf.cz.  It's
quick, easy and FREE. Use the following link to register.

  http://bit.ly/devconf-cz-2017-registration


Slides
------

We recommend posting your slides somewhere on-line once they're ready, tweeting
about them with #devconfcz #defineFUTURE tags and including a link back to them
on the first and last slide of your deck. You could host them over at github.com
or slideshare.net, for example.


Speaker Hotel Reservations
--------------------------
DevConf.cz offers traveling *speakers* free accommodation for up to 3 nights at
Hotel Avanti:
 * Thursday Jan 26
 * Friday Jan 27
 * Saturday Jan 28

Hotel Avanti is near the venue and the main tram lines, beautiful rooms with
WiFi, free breakfast and parking and has an recently been upgraded to include
free access to their new wellness center!

** Sharing a double room with another speaker is strongly recommended! **

To secure your reservation, send an email ASAP with the following information
TO: hotel@hotelavanti.cz
CC: info@devconf.com
SUBJECT: DevConf.cz Speaker Reservation - $your_name

 * Whether you are requesting a single / double *classic* room
 * names of people
 * check-in / check-out dates
   - DevConf.cz will cover *ONLY*
     + up to 3 nights of Jan 26-28
     + Accepted DevConf.cz speakers (ie, you ;)
   - you are responsible for payment of additional fees for
      - *all* additional nights
      - non-speakers
      - mini-bar use, etc

If you do plan to stay longer than Thursday 26, Friday 27, Saturday 28, great!
Book your reservation as per the above instructions. DevConf.cz will arrange
things with the Hotel to cover those nights for you. Then, the rest of the bill
will be split out at check-out (your departure) and all additional accommodation
fees *must be* covered separately by *you*.

If Hotel Avanti runs out of space for some reason, contact info@redhat.com
and we'll figure out how to handle the situation.

**********************************************************************
  If you choose to reserve your hotel somewhere other than Avanti,
      DevConf.cz will NOT cover your accommodation expenses!
**********************************************************************


Travel Funding
--------------

DevConf.cz does not cover travel expenses, nor do we offer financial aid or
other financial support beyond covering accommodation as mentioned above.



If you think there has been a mistake, have any other requests, questions or
concerns just let us know with a quick reply to this mail.

See you soon at DevConf.cz 2017!

-- Chris and the rest of the DevConf.cz 2017 organizing team --


Email us at: info@devconf.cz

Subscribe to our newsletter for important event updates!
 * https://tinyletter.com/devconf_cz

Stop by during the event to say HELLO WORLD on Telegram:
 * https://telegram.me/joinchat/B1He_UEkuB4fBfY1cKCXRw

Follow us and what other's are tweeting about the event!
 * https://twitter.com/devconf_cz
 * hashtags: #devconf_cz #DEFINEfuture

'''


@cli.command()
@click.pass_obj
def schedule(obj):
    db_url = '1hpmxiUJ3DwkbEUdOfEFo2CmIZVWU2w6oYz4B5MEJZDU'
    speakers_wks = 'speakers'
    submissions_wks = 'submissions'
    sched_url = '1xi3QpEhIx3R600ZvKpbEPJ5D-z5o9j5fMHMFpFb_hPw'
    sched_wks = 'All Sessions'

    print('Getting Speakers DB...')
    speakers_db = pd.read_csv(
        '/home/cward/Downloads/DevConf.cz - MASTER db - speakers.csv')

    print('Getting Submissions DB...')
    submissions_db = pd.read_csv(
        '/home/cward/Downloads/DevConf.cz - MASTER db - submissions.csv')

    print('Getting Submissions...')
    sched = pd.read_csv(
        '/home/cward/Downloads/DevConf.cz 2017 - Program Draft - All Sessions.csv')

    print('Getting all original submissions')
    source_db = pd.read_csv(
        '/home/cward/Downloads/Devconf.cz CfP Submissions - SOURCE - CLEAN Talks MASTER.csv')

    print('Processing data...')

    # get a full list of all accepted speakers
    sched['speakers'] = sched.speakers.map(
        lambda x: [y.strip() for y in x.split(';')])

    # print out the speaker session counts
    speakers_k = Counter()
    for _ in sched.speakers.to_dict().values():
        for spkr in _:
            speakers_k.update({spkr: 1})

    # pull out a list of the unique speakers
    speakers = sorted(speakers_k.keys())

    print()

    print('Speakers with > 1 talk')
    for spkr, k in speakers_k.items():
        if k > 1:
            print(' {}: {}'.format(spkr, k))

    print()

    print('Speaker Countries')
    # print out the speaker country counts
    countries_k = Counter()
    for spkr in speakers:
        person = speakers_db[speakers_db.email == spkr]
        country = person.country
        if not country.any():
            countries_k.update({'unknown': 1})
        else:
            countries_k.update({country.values[0]: 1})
    for x, y in sorted(countries_k.items()):
        print('{: <3} x {}'.format(y, x))

    print()

    print('Speaker Orgs')
    # print out the speaker country counts
    orgs_k = Counter()
    for spkr in speakers:
        person = speakers_db[speakers_db.email == spkr]
        org = person.org
        if not org.any():
            orgs_k.update({'unknown': 1})
        else:
            orgs_k.update({org.values[0]: 1})
    for x, y in sorted(orgs_k.items()):
        print('{: <3} x {}'.format(y, x))

    print()

    # duplicate talks?
    accepted = sorted(sched.session_id.values)
    accepted_k = Counter()
    for x in accepted:
        accepted_k.update({x: 1})
    print('ACCEPTED ids:')
    for x, y in sorted(accepted_k.items()):
        print('{: <3} x {}'.format(y, x))

    print()

    print("ACCEPTED SPEAKERS SUMMARY")
    # accepted speaker summary
    speakers_list = []
    for _ in speakers:
        if _ == 'shadowman':
            continue
        spkr = speakers_db[speakers_db.email == _]
        name = spkr.name.values[0]
        country = spkr.country.values[0]
        org = spkr.org.values[0]
        speakers_list.append({'name': name, 'country': country, 'org': org})

    for i in sorted(speakers_list, key=lambda x: (x['org'], x['name'])):
        print('{: <25} @ {: <15}: {}'.format(
            i['name'], i['org'], i['country']))

    print()

    print('Total sessions: {}'.format(len(accepted)))
    print('Total speakers: {}'.format(len(speakers)))

    def rejected():
        # rejected talks
        all_submissions = set([int(x) for x in submissions_db.id.values])
        rejected = []
        for i in all_submissions:
            if i not in accepted:
                rejected.append(i)
        print('REJECTED: {}'.format(rejected))
        rejecteds = []
        for _id in rejected:
            item = submissions_db[submissions_db.id == int(_id)]
            title = item.title.values[0]
            speaker = item.name.values[0][0:22] + '...'
            org = item.org.values[0][:12] + '...'
            _type = item.type.values[0][:12] + '...'
            rejecteds.append({'id': _id, 'speaker': speaker,
                             'org': org, 'type': _type})
            print('[{: <3}] {: <25} @ {: <15}: ({: <15}) {}'.format(
                _id, speaker, org, _type, title))
    #rejected()


    #import ipdb; ipdb.set_trace()


if __name__ == '__main__':
    cli(obj={})
