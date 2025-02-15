from dataclasses import dataclass
from datetime import datetime
from logging import getLogger
from os import getenv
from pathlib import Path
from xml.etree import ElementTree

from dateutil.parser import parse as parse_date
from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth

load_dotenv()
NC_USER = getenv('NC_USER')
NC_DIR = getenv('NC_DIR')
NC_BASE_URL = f'https://{getenv("NC_HOST")}/remote.php/dav/files/{NC_USER}/{NC_DIR}'
NC_SESSION = Session()
NC_SESSION.auth = HTTPBasicAuth(NC_USER, getenv('NC_PASS'))

logger = getLogger(__name__)


@dataclass
class RemoteFile:
    name: str
    mtime: datetime

    @classmethod
    def from_xml(cls, element) -> 'RemoteFile':
        return cls(
            name=element.find('.//{DAV:}href').text,
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
