from logging import basicConfig, getLogger
from os import getenv
from pathlib import Path

import requests
from dotenv import load_dotenv
from requests.auth import HTTPBasicAuth

load_dotenv()
NC_USER = getenv('NC_USER')
NC_DIR = getenv('NC_DIR')
BASE_URL = f'https://{getenv("NC_HOST")}/remote.php/dav/files/{NC_USER}/{NC_DIR}'
SESSION = requests.Session()
SESSION.auth = HTTPBasicAuth(NC_USER, getenv('NC_PASS'))

logger = getLogger(__name__)
basicConfig(level='DEBUG')


def webdav_upload(local_paths: list[Path], remote_path: Path):
    """Upload files to Nextcloud via WebDAV"""
    _webdav_mkdir()
    for local_path in local_paths:
        response = SESSION.put(
            f'{BASE_URL}/{remote_path}',
            # data=local_path.read_bytes(),
            data=b'Hello, World!',
        )

    if response.ok:
        logger.debug(f'Uploaded {local_path} -> {BASE_URL}/{remote_path}')
    else:
        logger.error(f'Error uploading {local_path}: {response.status_code} {response.text}')


def _webdav_mkdir():
    """Create the remote folder if it doesn't already exist"""
    response = SESSION.request('MKCOL', BASE_URL)
    if response.status_code == 201:
        logger.debug(f'Folder {NC_DIR} created')
    elif response.status_code == 405:
        logger.debug(f'Folder {NC_DIR} already exists')
    else:
        logger.error(f'Error creating {NC_DIR}: {response.status_code} {response.text}')


# webdav_upload([Path('test.txt')], Path('test.txt'))


# WIP: ls function
# Adapted from: https://github.com/amnong/easywebdav/blob/master/easywebdav/client.py
from dataclasses import dataclass
from xml.etree import ElementTree


@dataclass
class RemoteFile:
    name: str
    size: int
    mtime: str
    ctime: str
    contenttype: str
    etag: str
    is_dir: bool

    @classmethod
    def from_xml(cls, element):
        def get_prop(name) -> str:
            child = element.find(f'.//{{DAV:}}{name}')
            return child.text if child is not None else ''

        return cls(
            name=get_prop('href'),
            size=int(get_prop('getcontentlength') or 0),
            mtime=get_prop('getlastmodified'),
            ctime=get_prop('creationdate'),
            contenttype=get_prop('getcontenttype'),
            etag=get_prop('getetag'),
            is_dir=element.find('.//{DAV:}collection') is not None,
        )


def webdav_ls() -> list[RemoteFile]:
    response = SESSION.request('PROPFIND', BASE_URL, headers={'Depth': '1'})
    xml_response = ElementTree.fromstring(response.content).findall('{DAV:}response')
    return [RemoteFile.from_xml(element) for element in xml_response]


files = webdav_ls()
for f in files:
    print(f)
