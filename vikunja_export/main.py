#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "dotenv",
#     "environ-config",
#     "html2text",
#     "python-dateutil",
#     "requests",
# ]
# ///
from logging import getLogger

from .config import CONFIG
from .vikunja import get_tasks
from .webdav import webdav_delete, webdav_ls, webdav_mkdir, webdav_rename, webdav_upload

logger = getLogger(__name__)


def main():
    """Check source tasks against existing destination files to run the minimal set of file
    operations. I.e., remove, rename, or create/update instead of bulk delete/recreate.
    """
    tasks = list(get_tasks())
    webdav_mkdir(CONFIG.nc_base_url)
    remote_files = webdav_ls()

    # Write summary file, if changes have been made
    summary_file = next((file for file in remote_files if file.filename == 'tasks.md'), None)
    if not summary_file or summary_file.mtime < max(task.mtime for task in tasks):
        combined_summary = '\n'.join(task.summary for task in tasks)
        webdav_upload(combined_summary, 'tasks.md')

    src_tasks = {task.id: task for task in tasks if task.detail}
    dest_tasks = {file.id: file for file in remote_files if file.filename[0].isdigit()}
    src_ids = set(src_tasks.keys())
    dest_ids = set(dest_tasks.keys())

    # Remove any remote tasks that don't exist in source
    to_remove = dest_ids - src_ids
    for task_id in to_remove:
        webdav_delete(dest_tasks[task_id].filename)

    # Rename any dest files that have changed in source
    to_rename = {k for k in src_ids & dest_ids if src_tasks[k].filename != dest_tasks[k].filename}
    for task_id in to_rename:
        webdav_rename(dest_tasks[task_id].filename, src_tasks[task_id].filename)

    # Update any dest files that have changed in source
    def has_changed(dt1, dt2):
        return (dt1 - dt2).total_seconds() > 5

    # Upload new and changed files
    to_update = {
        k for k in src_ids & dest_ids if has_changed(src_tasks[k].mtime, dest_tasks[k].mtime)
    }
    new = src_ids - dest_ids
    for task_id in to_update | new:
        webdav_upload(src_tasks[task_id].detail, src_tasks[task_id].filename)

    unchanged = (src_ids & dest_ids) - (to_rename | to_update)
    logger.info(
        'Export complete:\n'
        f'  New: {len(new)}\n'
        f'  Updated: {len(to_rename | to_update)}\n'
        f'  Removed: {len(to_remove)}\n'
        f'  Unchanged: {len(unchanged)}\n'
    )


if __name__ == '__main__':
    main()
