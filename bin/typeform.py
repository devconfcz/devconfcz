#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Installation (Python 3)
-----------------------

    virtualenv -p python3 ~/virtenvs/devconfcz/
    source ~/virtenvs/devconfcz/bin/activate
    pip install hyde requests click


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

from collections import defaultdict
import datetime
import json
import os
import requests
import time

import click  # http://click.pocoo.org/6/


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

SPEAKER_FIELDS = ['agreement', 'name', 'country', 'bio', 'org', 'size',
                  'email', 'avatar', 'twitter', 'secondary']

SESSION_FIELDS = ['title', 'type', 'theme', 'difficulty', 'abstract']

DEFAULT_SAVE_PATH = './proposals.json'


## Shared Functions

def _clean_twitter(handle):
    handle = str(handle or "")  # makes sure we're working with a string
    handle = handle.lstrip('@')  # clear any existing @ if present
    handle = handle.split('/')[-1]  # grab handle only in case of https://...
    # assume 1c handles are invalid
    handle = handle if len(handle) > 1 else ""  
    return handle


def _get_json(url, params):
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
        dt = response['metadata']['date_submit']
        # dt = datetime.datetime.strptime(dt, '%y-%m-%d %H:%M:%S')
        _id = (response['metadata']['network_id'] + '+' + dt).replace(' ', '')

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
            proposal['theme'] = sorted(proposal['theme'])
            proposals.append(proposal)

    # Reverse Sort by date submitted
    proposals = sorted(proposals, key=lambda x: x['submitted'], reverse=True)

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

def _show_stats(obj):
    """ Calculate and show some basic resource stats """
    # Speakers and Sessions: Total
    # Speakers: 
    # * unique: org, country
    # Sessions:
    # * unique: type, theme, difficulty

    stats = {}
    template = """Sessions"""

    keys = {
        "sessions": ['type', 'theme', 'difficulty'],
        "speakers": ['org', 'country'],
    }

    stats['speakers'] = defaultdict(list)
    stats['sessions'] = defaultdict(list)
    for resource_type in ['speakers', 'sessions']:
        for resource in obj[resource_type]:
            for key in keys[resource_type]:
                stats[resource_type][key].append(
                    resource.get(key, 'UNKNOWN'))
        
        


def _show_resources(proposals, summary):
    """Echo form responses Human Readable form to STDOUT"""
    template = """
Title:      {title}
Speaker:    {speaker}
Email:      {email}
Type:       {type}
Theme:      {theme}
Difficulty: {difficulty}
Submitted:  {submitted}
""".strip()

    if not summary:
        template += """\nAbstract:\n\n{abstract}"""

    template += "\n\n" + "-" * 79 + "\n"

    for proposal in proposals:
        speaker = proposal['name']
        twitter = proposal.get('twitter')
        if twitter and len(twitter) > 1:
            speaker += ' (@{})'.format(twitter)
        click.echo(template.format(speaker=speaker, **proposal))


def _get_resources(resource, proposals):
    if resource == "proposals":
        return proposals  # return as-is
    elif resource == "sessions":
        keys = SESSION_FIELDS
    elif resource == "speakers":
        keys = SPEAKER_FIELDS
    else:
        raise ValueError("Invalid resource: {}".format(resource))

    resources = []
    for proposal in proposals:
        _id = proposal['_id']
        item = {'_id': _id}
        secondary = {} 
        for key in keys:
            if key == 'secondary' and proposal.get(key):
                # Secondary speakers are just blobs; need manual processing
                secondary['_secondary'] = True
                secondary['_id'] = _id
                secondary['_raw'] = proposal.get(key)
            else:
                item[key] = proposal.get(key, None)

        resources.append(item)

        if secondary:
            resources.append(secondary)

    return resources


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

    proposals = _get_json(url, params)
    sessions = _get_resources('sessions', proposals)
    speakers = _get_resources('speakers', proposals)

    ctx.obj['sessions'] = sessions
    ctx.obj['speakers'] = speakers


@cli.command()
@click.option('--path', default=DEFAULT_SAVE_PATH, help='Output Path')
@click.pass_obj
def save(obj, path):
    proposals = obj['proposals']
    f = open(path, 'w')
    json.dump(proposals, f, sort_keys=True, indent=2, separators=(',', ': '))


@cli.command()
@click.argument('resource', default='sessions', 
                type=click.Choice(['sessions', 'speakers', 'proposals']))
@click.option('--summary', default=False, is_flag=True,
              help='Show only short summary of data')
@click.pass_obj
def show(obj, resource, summary):
    resources = obj[resource]
    _show_resources(resources, summary)


@cli.command()
@click.argument('resource', default='sessions', 
                type=click.Choice(['sessions', 'speakers', 'proposals']))
@click.pass_obj
def count(obj, resource):
    resources = obj[resource]
    click.echo(len(resources))


@cli.command()
@click.pass_obj
def stats(obj):
    _show_stats(obj)


# TODO
# cache results
# cache avatars


if __name__ == '__main__':
    cli(obj={})
