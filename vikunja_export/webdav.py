"""Utilities to interact with a remote Nextcloud server via WebDAV API.

Note: If needed, this could be easily adapted to work with any WebDAV server.
"""

from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from pathlib import Path
from xml.etree import ElementTree

from dateutil.parser import parse as parse_date

from .config import NC_BASE_URL, NC_DIR, NC_SESSION

logger = getLogger(__name__)


@dataclass
class RemoteFile:
    id: int
    path: str
    filename: str
    mtime: datetime

    @classmethod
    def from_xml(cls, element) -> 'RemoteFile':
        path = element.find('.//{DAV:}href').text
        return cls(
            id=int(path.split('_')[0]),
            path=path,
            filename=path.split('/')[-1],
            mtime=parse_date(element.find('.//{DAV:}getlastmodified').text),
        )


def webdav_ls() -> list[RemoteFile]:
    """List all files in the remote directory"""
    response = NC_SESSION.request('PROPFIND', NC_BASE_URL, headers={'Depth': '1'})
    xml_response = ElementTree.fromstring(response.content).findall('{DAV:}response')
    return [RemoteFile.from_xml(element) for element in xml_response if not _is_dir(element)]


def _is_dir(element) -> bool:
    return element.find('.//{DAV:}collection') is not None


def webdav_upload(local_paths: list[Path], remote_path: Path):
    """Upload files to Nextcloud via WebDAV"""
    _webdav_mkdir()
    for local_path in local_paths:
        response = NC_SESSION.put(
            f'{NC_BASE_URL}/{remote_path}',
            data=local_path.read_bytes(),
        )

    if response.ok:
        logger.debug(f'Uploaded {local_path} -> {NC_BASE_URL}/{remote_path}')
    else:
        logger.error(f'Error uploading {local_path}: {response.status_code} {response.text}')


def webdav_rename(src_path, dest_path):
    """Rename a file on the remote server"""
    response = NC_SESSION.request(
        'MOVE', f'{NC_BASE_URL}/{src_path}', headers={'Destination': f'{NC_BASE_URL}/{dest_path}'}
    )
    if response.status_code == 201:
        logger.debug(f'Renamed {src_path} -> {dest_path}')
    else:
        logger.error(f'Error renaming {src_path}: {response.status_code} {response.text}')


def webdav_delete(remote_path):
    """Delete a file on the remote server"""
    response = NC_SESSION.delete(f'{NC_BASE_URL}/{remote_path}')
    if response.status_code == 204:
        logger.debug(f'Deleted {remote_path}')
    else:
        logger.error(f'Error deleting {remote_path}: {response.status_code} {response.text}')


def _webdav_mkdir():
    """Create the remote folder if it doesn't already exist"""
    response = NC_SESSION.request('MKCOL', NC_BASE_URL)
    if response.status_code == 201:
        logger.debug(f'Folder {NC_DIR} created')
    elif response.status_code == 405:
        logger.debug(f'Folder {NC_DIR} already exists')
    else:
        logger.error(f'Error creating {NC_DIR}: {response.status_code} {response.text}')


# webdav_upload([Path('test.txt')], Path('test.txt'))
# print(webdav_ls())
