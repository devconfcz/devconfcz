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
EOT

"""

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
    'Speaker Agreement': 'Agreement',
    'Session Title': 'Title',
    'Session Type': 'Type',
    'Session Theme': 'Theme',
    'Session Difficulty': 'Difficulty',
    'Session Abstract / Description': 'Abstract',
    'What\'s the primary speakers name?': 'Name',
    'Where is the primary speaker traveling from?': 'Country',
    'Primary speakers background / bio?': 'Bio',
    'Primary Speaker\'s Organizational Affiliation': 'Org',
    'Primary Speakers wearables size?': 'Size',
    'Primary speaker\'s email address?': 'Email',
    'Link to primary speaker\'s \xa0Avatar / Profile Pic': 'Avatar',
    'Primary Speaker\'s Twitter handle?': 'Twitter',
    'Secondary Speaker Info': 'Secondary',
}

SPEAKER_FIELDS = ['Agreement', 'Name', 'Country', 'Bio', 'Org', 'Size',
                  'Email', 'Avatar', 'Twitter', 'Secondary']

SESSION_FIELDS = ['Title', 'Type', 'Theme', 'Difficulty', 'Abstract']

DEFAULT_SAVE_PATH = './proposals.json'


## Shared Functions

def __get_speaker(name, twitter):
    twitter = (twitter or "")  # makes sure we're working with a string
    twitter = twitter.lstrip('@')  # clear any existing @ if present
    twitter = twitter.split('/')[-1]  # grab handle only in case of https://...
    if twitter and len(twitter) > 1:
        name += ' (@{})'.format(twitter)
    return name


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

        # Save the submission date
        proposal = {'Submitted': dt}
        # Gonna aggregate multiple themes into a single list
        proposal['Theme'] = []

        for field, value in answers.items():
            value = value.strip()
            # Grab the actual (though unreadable) form label id
            _field = questions[field]
            # Swap it with the simplified field alias for dict keys
            alias = QUESTION_ALIAS[_field]

            if alias == 'Theme':
                proposal[alias].append(value)
            else:
                proposal[alias] = value

        else:
            proposal['Theme'] = sorted(proposal['Theme'])
            proposals.append(proposal)

    # Reverse Sort by date submitted
    proposals = sorted(proposals, key=lambda x: x['Submitted'], reverse=True)

    return proposals


def __convert_datetime(dt):
    dt_format = '%Y-%m-%d'

    if dt == 'today':
        dt = str(datetime.date.today())
    elif dt == 'yesterday':
        dt = str(
            datetime.date.fromordinal(datetime.date.today().toordinal() - 1))

    epoch = time.mktime(time.strptime(dt, dt_format))

    return int(epoch)


def _echo_stdout(proposals, with_abstract):
    """Download and echo the form responses Human Readable form to STDOUT"""
    template = """
Speaker:    {Speaker}
Submitted:  {Submitted}
Title:      {Title}
Type:       {Type}
Theme:      {Theme}
Difficulty: {Difficulty}""".strip()

    if with_abstract:
        template += """\nAbstract:\n\n{Abstract}"""

    template += "\n" + "-" * 79 + "\n"

    for proposal in proposals:
        speaker = __get_speaker(proposal['Name'], proposal.get('Twitter'))
        click.echo(template.format(Speaker=speaker, **proposal))


## CLI Set-up ##

@click.group()
@click.option('--since', default=None, help='Filter by submission date')
@click.pass_context
def cli(ctx, since):
    """Download and save the form responses in JSON"""

    # Apply Filters
    if since:
        # convert to UNIX timestamp
        since = __convert_datetime(since)
        params['since'] = since

    proposals = _get_json(url, params)

    # Pass along the proposals to the remaining commands
    ctx.obj['proposals'] = proposals


@cli.command()
@click.option('--path', default=DEFAULT_SAVE_PATH, help='Output Path')
@click.pass_context
def save(ctx, path):
    proposals = ctx.obj['proposals']
    f = open(path, 'w')
    json.dump(proposals, f, sort_keys=True, indent=2, separators=(',', ': '))


@cli.command()
@click.option('--with-abstract', default=False, is_flag=True,
              help='Filter by submission date')
@click.pass_context
def show(ctx, with_abstract):
    proposals = ctx.obj['proposals']
    _echo_stdout(proposals, with_abstract)


@cli.command()
@click.pass_context
def count(ctx):
    proposals = ctx.obj['proposals']

    click.echo(len(proposals))


if __name__ == '__main__':
    cli(obj={})
