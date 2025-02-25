"""Utilities to fetch, convert, and format task data from Vikunja"""

import re
from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from textwrap import dedent
from typing import Iterator

from dateutil.parser import parse as parse_date
from html2text import HTML2Text

from .config import CONFIG, VJA_SESSION

# Settings from environment variables and/or .env file
API_BASE_URL = f'https://{CONFIG.vja_host}/api/v1'
TASK_BASE_URL = f'https://{CONFIG.vja_host}/tasks'
DT_FORMAT = '%Y-%m-%d'

logger = getLogger(__name__)


@dataclass
class Task:
    id: int
    filename: str
    mtime: datetime
    detail: str
    summary: str


def get_tasks() -> Iterator[Task]:
    """Get all tasks add comments and projects, and format for export"""
    logger.info('Fetching tasks')
    tasks = _paginate(f'{API_BASE_URL}/tasks/all')
    logger.debug('Fetching projects')
    projects = _paginate(f'{API_BASE_URL}/projects')
    projects = {p['id']: p['title'] for p in projects}

    # Add comments and project titles
    logger.debug('Fetching comments')
    for task in tasks:
        response = VJA_SESSION.get(f'{API_BASE_URL}/tasks/{task["id"]}/comments')
        task['comments'] = response.json()
        if project_id := task.pop('project_id', None):
            task['project'] = projects[project_id]
        if not task.get('labels'):
            task['labels'] = []

    # Filter out ignored projects and labels
    logger.debug(f'Ignoring projects {CONFIG.ignore_projects} and labels {CONFIG.ignore_labels}')
    total_tasks = len(tasks)
    tasks = [
        t
        for t in tasks
        if t['project'] not in CONFIG.ignore_projects
        and all(lbl['title'] not in CONFIG.ignore_labels for lbl in t['labels'])
    ]
    logger.info(f'Found {len(tasks)} tasks ({total_tasks - len(tasks)} ignored)')

    for task in tasks:
        yield Task(
            id=int(task['id']),
            filename=get_task_filename(task),
            mtime=parse_date(task['updated']),
            detail=get_task_detail(task),
            summary=get_task_summary(task),
        )


def _paginate(url: str):
    """Get all pages from a paginated API endpoint"""
    response = VJA_SESSION.get(url)
    response.raise_for_status()
    total_pages = int(response.headers['x-pagination-total-pages'])
    records = response.json()
    for page in range(2, total_pages + 1):
        response = VJA_SESSION.get(url, params={'page': page})
        response.raise_for_status()
        records += response.json()
    return records


def get_task_filename(task: dict) -> str:
    normalized_title = re.sub(r'[^\w\s]', '', task['title']).strip().replace(' ', '_')
    return f'{task["id"]}_{normalized_title}.md'


def get_task_detail(task: dict) -> str:
    if not task['description'] and not task['comments']:
        return ''

    labels = ', '.join([label['title'] for label in task['labels'] or []])
    completed_dt = parse_date(task['done_at']) if task['done'] else 'N/A'
    detail = [
        f'# {task["title"]}',
        f'* URL: {TASK_BASE_URL}/{task["id"]}',
        f'* Created: {_format_dt(task["created"])}',
        f'* Updated: {_format_dt(task["updated"])}',
        f'* Completed: {completed_dt}',
        f'* Project: {task["project"]}',
        f'* Labels: {labels}',
    ]
    if task['description']:
        detail += [
            '\n# Description',
            _convert_text(task['description']),
        ]
    if task['comments']:
        detail.append('\n# Comments')
        for comment in task['comments']:
            detail += [
                f'\n## {comment["author"]["name"]} {_format_dt(comment["created"])}',
                _convert_text(comment['comment']),
            ]

    return '\n'.join(detail)


def get_task_summary(task: dict) -> str:
    labels = ' '.join([f'[{label["title"]}]' for label in task['labels']])
    check = '✅ ' if task['done'] else '   '
    return (
        f'{task["id"]:0>4}{check}: {task["project"]} / {task["title"]} {labels} {task["created"]}'
    )


def _convert_text(text: str) -> str:
    """Convert HTML content to Markdown"""
    md_text = HTML2Text().handle(text)
    return dedent(md_text).strip()


def _format_dt(timestamp: str) -> str:
    return parse_date(timestamp).strftime(DT_FORMAT) if timestamp else 'N/A'
