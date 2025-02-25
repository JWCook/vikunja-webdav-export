"""Load settings from environment variables and/or .env file"""

from logging import basicConfig, getLogger
from os import getenv
from pathlib import Path

import environ
from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth


def split_list(list_str: str) -> list[str]:
    return [s.strip() for s in list_str.split(',')]


def resolve_path(p: str) -> Path:
    return Path(p).expanduser().absolute()


@environ.config(prefix=None)
class EnvConfig:
    log_level = environ.var(default='INFO')

    # Vikunja settings
    vja_host = environ.var()
    vja_token = environ.var()
    ignore_projects = environ.var(converter=split_list)
    ignore_labels = environ.var(converter=split_list)

    # Nextcloud/WebDAV settings
    nc_user = environ.var()
    nc_dir = environ.var()
    nc_host = environ.var()

    @property
    def nc_base_url(self):
        return f'https://{self.nc_host}/remote.php/dav/files/{self.nc_user}/{self.nc_dir}'


# First load .env (if it exists), then read environment variables
load_dotenv()
CONFIG = environ.to_config(EnvConfig)

VJA_SESSION = Session()
VJA_SESSION.headers = {'Authorization': f'Bearer {CONFIG.vja_token}'}

NC_SESSION = Session()
NC_SESSION.auth = HTTPBasicAuth(CONFIG.nc_user, getenv('NC_PASS'))

basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)-5s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=CONFIG.log_level,
)
getLogger('urllib3').setLevel('WARN')
