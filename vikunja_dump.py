#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "requests",
#     "html2text",
# ]
# ///
import re
from os import getenv
from logging import getLogger, basicConfig
from pathlib import Path
from shutil import rmtree
from textwrap import dedent

from html2text import HTML2Text
from requests import Session

API_HOST = getenv('VIKUNJA_HOST', 'try.vikunja.io')
API_BASE_URL = f'https://{API_HOST}/api/v1'
TASK_BASE_URL = f'https://{API_HOST}/tasks'
HEADERS = {'Authorization': f'Bearer {getenv("VIKUNJA_TOKEN")}'}
IGNORE_PROJECTS = []
OUTPUT_DIR = Path('output')
SESSION = Session()

logger = getLogger(__name__)
basicConfig(level='INFO')


def get_tasks():
    logger.info('Fetching tasks')
    tasks = paginate(f'{API_BASE_URL}/tasks/all')
    logger.info('Fetching projects')
    projects = paginate(f'{API_BASE_URL}/projects')
    projects = {p['id']: p['title'] for p in projects}

    # Add comments and project titles
    logger.info('Fetching comments')
    for task in tasks:
        response = SESSION.get(f'{API_BASE_URL}/tasks/{task["id"]}/comments', headers=HEADERS)
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

    # Filter out ignored projects
    total_tasks = len(tasks)
    tasks = [task for task in tasks if task['project'] not in IGNORE_PROJECTS]
    msg = f'Found {len(tasks)} tasks'
    if n_ignored := total_tasks - len(tasks):
        msg += f'{n_ignored} tasks ignored'
    logger.info(msg)
    return tasks


def convert_text(text: str):
    """Convert HTML content to Markdown"""
    md_text = HTML2Text().handle(text)
    return dedent(md_text).strip()


def paginate(url: str):
    """Get all pages from a paginated API endpoint"""
    response = SESSION.get(url, headers=HEADERS)
    response.raise_for_status()
    total_pages = int(response.headers['x-pagination-total-pages'])
    records = response.json()
    for page in range(2, total_pages + 1):
        response = SESSION.get(url, headers=HEADERS, params={'page': page})
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
    normalized_title = re.sub(r'[^\w\s]', '', task['title']).replace(' ', '_')
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
    rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = get_tasks()
    logger.info(f'Found {len(tasks)} tasks')

    # with (OUTPUT_DIR / 'all_tasks.json').open('w') as f:
    #     f.write(json.dumps(tasks, indent=2))
    write_task_summary(tasks)

    detail_tasks = [task for task in tasks if task['description'] or task['comments']]
    for task in detail_tasks:
        write_task_detail(task)
    logger.info(f'Found {len(detail_tasks)} tasks with details')


if __name__ == '__main__':
    main()
