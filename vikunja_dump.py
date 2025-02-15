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
from datetime import datetime
from logging import basicConfig, getLogger
from os import getenv
from pathlib import Path
from textwrap import dedent

from dotenv import load_dotenv
from html2text import HTML2Text
from requests import Session

# Settings from environment variables and/or .env file
load_dotenv()
API_HOST = getenv('VJA_HOST')
API_TOKEN = getenv('VJA_TOKEN')
IGNORE_PROJECTS = [s.strip() for s in getenv('VJA_IGNORE_PROJECTS', '').split(',')]
IGNORE_LABELS = [s.strip() for s in getenv('VJA_IGNORE_LABELS', '').split(',')]
COMBINED_JSON = getenv('VJA_COMBINED_JSON', 'False').lower() == 'true'
LOG_LEVEL = getenv('VJA_LOG_LEVEL', 'WARN')
OUTPUT_DIR = Path(getenv('VJA_OUTPUT_DIR', 'output')).expanduser().absolute()

API_BASE_URL = f'https://{API_HOST}/api/v1'
TASK_BASE_URL = f'https://{API_HOST}/tasks'
KEEP_FIELDS = [
    'id',
    'title',
    'filename',
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
SRC_DT_FORMAT = '%Y-%m-%dT%H:%M:%S'
OUTPUT_DT_FORMAT = '%Y-%m-%d'
VJA_SESSION = Session()
VJA_SESSION.headers = {'Authorization': f'Bearer {API_TOKEN}'}

basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)-5s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level='WARN',
)
logger = getLogger('vikunja-dump')
logger.setLevel(LOG_LEVEL)


def main():
    if not API_HOST:
        raise ValueError('API host required')
    if not API_TOKEN:
        raise ValueError('API token required')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    tasks = get_tasks()

    if COMBINED_JSON:
        with (OUTPUT_DIR / 'tasks.json').open('w') as f:
            f.write(json.dumps(tasks, indent=2))
    else:
        write_task_summary(tasks)
        detail_tasks = [task for task in tasks if task['description'] or task['comments']]
        logger.info(f'Found {len(detail_tasks)} tasks with details')
        update_paths(detail_tasks)
        for task in detail_tasks:
            write_task_detail(task)

    logger.info(f'Export complete: {OUTPUT_DIR}')


def get_tasks():
    """Get all tasks add comments and projects, and format for export"""
    logger.info('Fetching tasks')
    tasks = paginate(f'{API_BASE_URL}/tasks/all')
    logger.debug('Fetching projects')
    projects = paginate(f'{API_BASE_URL}/projects')
    projects = {p['id']: p['title'] for p in projects}

    # Add comments and project titles
    logger.debug('Fetching comments')
    for task in tasks:
        response = VJA_SESSION.get(f'{API_BASE_URL}/tasks/{task["id"]}/comments')
        task['comments'] = response.json()
        for comment in task['comments']:
            comment['comment'] = _convert_text(comment['comment'])
            comment['created'] = _format_dt(comment['created'])
        if project_id := task.pop('project_id', None):
            task['project'] = projects[project_id]

        # Format other relevant fields
        labels = task['labels'] or []
        task['labels'] = [label['title'] for label in labels]
        task['description'] = _convert_text(task['description'])
        task['created'] = _parse_dt(task['created'])
        task['updated'] = _parse_dt(task['updated'])
        task['done_at'] = _parse_dt(task['done_at']) if task['done'] else 'N/A'
        normalized_title = re.sub(r'[^\w\s]', '', task['title']).strip().replace(' ', '_')
        task['filename'] = f'{task["id"]}_{normalized_title}.md'

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


def paginate(url: str):
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


def _convert_text(text: str) -> str:
    """Convert HTML content to Markdown"""
    md_text = HTML2Text().handle(text)
    return dedent(md_text).strip()


def _parse_dt(timestamp: str) -> datetime | None:
    return datetime.strptime(timestamp, SRC_DT_FORMAT) if timestamp else None


def _format_dt(dt: datetime | None) -> str:
    return dt.strftime(OUTPUT_DT_FORMAT) if dt else 'N/A'


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


def write_task_detail(task: dict):
    detail = [
        f'# {task["title"]}',
        f'* URL: {TASK_BASE_URL}/{task["id"]}',
        f'* Created: {_format_dt(task["created"])}',
        f'* Updated: {_format_dt(task["updated"])}',
        f'* Completed: {_format_dt(task["done_at"])}',
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
                f'\n## {comment["author"]["name"]} {_format_dt(comment["created"])}',
                comment['comment'],
            ]

    with (OUTPUT_DIR / task['filename']).open('w') as f:
        f.write('\n'.join(detail))


# TODO: don't modify files if contents haven't changed?
def update_paths(tasks: dict):
    """Merge local and remote file paths so external sync programs pick up the correct file
    operations. I.e., rename/modify rather than delete/create.
    """
    task_paths = [path for path in OUTPUT_DIR.glob('*.md') if path.name[0].isdigit()]
    local_id_paths = {int(path.name.split('_')[0]): path for path in task_paths}
    remote_id_paths = {int(task['id']): OUTPUT_DIR / task['filename'] for task in tasks}

    # Remove any local ids that don't exist remotely
    to_remove = set(local_id_paths.keys()) - set(remote_id_paths.keys())
    for task_id in to_remove:
        local_id_paths[task_id].unlink()

    # Rename any local files that have changed remotely
    to_rename = {
        k
        for k in set(remote_id_paths.keys()) & set(local_id_paths.keys())
        if remote_id_paths[k].name != local_id_paths[k].name
    }
    for task_id in to_rename:
        local_id_paths[task_id].rename(remote_id_paths[task_id])

    logger.debug(
        f'Removed: {len(to_remove)} | Renamed: {len(to_rename)} | '
        f'Created: {len(set(remote_id_paths.keys()) - set(local_id_paths.keys()))}'
    )


def check_for_updates(tasks: dict) -> dict:
    """Check remote timestamps (task['updated']) against local file timestamps; remove any tasks
    that haven't changed.
    """
    task_paths = [path for path in OUTPUT_DIR.glob('*.md') if path.name[0].isdigit()]
    {path.name: path.stat().st_mtime for path in task_paths}
    {task['filename']: task['updated'] for task in tasks}


if __name__ == '__main__':
    main()
