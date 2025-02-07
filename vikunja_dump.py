#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "python-dotenv",
#     "requests",
#     "html2text",
# ]
# ///
import json
import re
from logging import basicConfig, getLogger
from os import getenv
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from html2text import HTML2Text
from requests import Session

# Options, settable from environment variables or .env file
load_dotenv()
API_HOST = getenv('VJA_HOST')
API_TOKEN = getenv('VJA_TOKEN')
IGNORE_PROJECTS = [s.strip() for s in getenv('VJA_IGNORE_PROJECTS', '').split(',')]
IGNORE_LABELS = [s.strip() for s in getenv('VJA_IGNORE_LABELS', '').split(',')]
COMBINED_JSON = getenv('VJA_COMBINED_JSON', 'False').lower() == 'true'
LOG_LEVEL = getenv('VJA_LOG_LEVEL', 'WARN')

API_BASE_URL = f'https://{API_HOST}/api/v1'
TASK_BASE_URL = f'https://{API_HOST}/tasks'
KEEP_FIELDS = [
    'id',
    'title',
    'description',
    'done',
    'done_at',
    'created',
    'updated',
    'is_favorite',
    'labels',
    'comments',
    'project',
]
OUTPUT_DIR = Path('output')
SESSION = Session()
SESSION.headers = {'Authorization': f'Bearer {API_TOKEN}'}

basicConfig(level='WARN')
logger = getLogger(__name__)
logger.setLevel(LOG_LEVEL)


def get_tasks():
    logger.info('Fetching tasks')
    tasks = paginate(f'{API_BASE_URL}/tasks/all')
    logger.info('Fetching projects')
    projects = paginate(f'{API_BASE_URL}/projects')
    projects = {p['id']: p['title'] for p in projects}

    # Add comments and project titles
    logger.info('Fetching comments')
    for task in tasks:
        response = SESSION.get(f'{API_BASE_URL}/tasks/{task["id"]}/comments')
        task['comments'] = response.json()
        for comment in task['comments']:
            comment['comment'] = convert_text(comment['comment'])
            comment['created'] = format_ts(comment['created'])
        if project_id := task.pop('project_id', None):
            task['project'] = projects[project_id]

        # Format other relevant fields
        labels = task['labels'] or []
        task['labels'] = [label['title'] for label in labels]
        task['description'] = convert_text(task['description'])
        task['created'] = format_ts(task['created'])
        task['updated'] = format_ts(task['updated'])
        task['done_at'] = format_ts(task['done_at']) if task['done'] else 'N/A'

        # Drop unused fields
        drop_fields = set(task.keys()) - set(KEEP_FIELDS)
        for k in drop_fields:
            task.pop(k)

    # Filter out ignored projects and labels
    logger.debug(f'Ignoring projects {IGNORE_PROJECTS} and labels {IGNORE_LABELS}')
    total_tasks = len(tasks)
    tasks = [
        t
        for t in tasks
        if t['project'] not in IGNORE_PROJECTS
        and all(lbl not in IGNORE_LABELS for lbl in t['labels'])
    ]
    msg = f'Found {len(tasks)} tasks'
    if n_ignored := total_tasks - len(tasks):
        msg += f' ({n_ignored} tasks ignored)'
    logger.info(msg)
    return tasks


def convert_text(text: str):
    """Convert HTML content to Markdown"""
    md_text = HTML2Text().handle(text)
    return dedent(md_text).strip()


def paginate(url: str):
    """Get all pages from a paginated API endpoint"""
    response = SESSION.get(url)
    response.raise_for_status()
    total_pages = int(response.headers['x-pagination-total-pages'])
    records = response.json()
    for page in range(2, total_pages + 1):
        response = SESSION.get(url, params={'page': page})
        response.raise_for_status()
        records += response.json()
    return records


def write_task_summary(tasks: dict):
    path = OUTPUT_DIR / 'tasks.md'
    with path.open('w') as f:
        for task in tasks:
            labels = ' '.join([f'[{label}]' for label in task['labels']])
            check = '✅ ' if task['done'] else '   '
            f.write(
                f'{task["id"]:0>4}{check}: {task["project"]} / {task["title"]} '
                f'{labels} {task["created"]}\n'
            )


def format_ts(ts: str):
    return ts.split('T')[0]


def write_task_detail(task: dict):
    normalized_title = re.sub(r'[^\w\s]', '', task['title']).strip().replace(' ', '_')
    path = OUTPUT_DIR / f'{task["id"]}_{normalized_title}.md'

    detail = [
        f'# {task["title"]}',
        f'* URL: {TASK_BASE_URL}/{task["id"]}',
        f'* Created: {task["created"]}',
        f'* Updated: {task["updated"]}',
        f'* Completed: {task["done_at"]}',
        f'* Project: {task["project"]}',
        f'* Labels: {", ".join(task["labels"])}',
    ]
    if task['description']:
        detail += [
            '\n# Description',
            task['description'],
        ]
    if task['comments']:
        detail.append('\n# Comments')
        for comment in task['comments']:
            detail += [
                f'\n## {comment["author"]["name"]} {comment["created"]}',
                comment['comment'],
            ]

    with path.open('w') as f:
        f.write('\n'.join(detail))


def main():
    if not API_HOST:
        raise ValueError('API host required')
    if not API_TOKEN:
        raise ValueError('API token required')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for f in OUTPUT_DIR.glob('*.md'):
        f.unlink()
    tasks = get_tasks()

    if COMBINED_JSON:
        with (OUTPUT_DIR / 'tasks.json').open('w') as f:
            f.write(json.dumps(tasks, indent=2))
    else:
        write_task_summary(tasks)
        detail_tasks = [task for task in tasks if task['description'] or task['comments']]
        logger.info(f'Found {len(detail_tasks)} tasks with details')
        for task in detail_tasks:
            write_task_detail(task)

    logger.info('Export complete')


if __name__ == '__main__':
    main()
