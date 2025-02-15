from logging import getLogger

from .vikunja import get_tasks
from .webdav import webdav_ls

logger = getLogger(__name__)


def main():
    """Check source tasks against existing destination files to run the minimal set of file
    operations. I.e., remove, rename, or create/update instead of bulk delete/recreate.
    """
    tasks = list(get_tasks())
    remote_files = webdav_ls()

    # Write summary file, if changes have been made
    summary_file = next((file for file in remote_files if file.filename == 'tasks.md'), None)
    if summary_file and summary_file.mtime > max(task.mtime for task in tasks):
        logger.info('No tasks have changed since last export')
        return
    '\n'.join(task.summary for task in tasks)
    # webdav_upload([combined_summary], 'tasks.md')

    # logger.info(f'Found {len(detail_tasks)} tasks with details')
    # logger.info(f'Export complete: {OUTPUT_DIR}')

    src_tasks = {task.id: task for task in tasks if task.detail}
    dest_tasks = {file.id: file.name for file in remote_files if file.name[0].isdigit()}
    src_ids = set(src_tasks.keys())
    dest_ids = set(dest_tasks.keys())

    # Remove any remote tasks that don't exist in source
    to_remove = dest_ids - src_ids
    # for task_id in to_remove:
    #     webdav_delete(dest_tasks[task_id])

    # Rename any dest files that have changed in source
    to_rename = {k for k in src_ids & dest_ids if src_tasks[k].name != dest_tasks[k].name}
    # for task_id in to_rename:
    #     webdav_rename(dest_tasks[task_id], src_tasks[task_id].name)

    # Update any dest files that have changed in source
    def has_changed(dt1, dt2):
        return abs((dt1 - dt2).total_seconds()) > 5

    to_update = {
        k for k in src_ids & dest_ids if has_changed(src_tasks[k].mtime, dest_tasks[k].mtime)
    }
    new = src_ids - dest_ids
    # for task_id in to_update | new:
    #     webdav_upload(src_tasks[task_id].path, src_tasks[task_id].name)

    unchanged = (src_ids & dest_ids) - (to_rename | to_update)

    logger.info(
        'Export complete:\n'
        f'  New: {len(new)}'
        f'  Updated: {len(to_rename | to_update)}\n'
        f'  Removed: {len(to_remove)}\n'
        f'  Unchanged: {len(unchanged)}\n'
    )
