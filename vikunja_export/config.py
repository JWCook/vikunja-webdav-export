"""Load settings from environment variables and/or .env file"""

from logging import basicConfig, getLogger
from os import getenv
from pathlib import Path

from dotenv import load_dotenv
from requests import Session
from requests.auth import HTTPBasicAuth

load_dotenv()


# Vikunja settings
VK_HOST = getenv('VK_HOST')
VK_TOKEN = getenv('VK_TOKEN')
IGNORE_PROJECTS = [s.strip() for s in getenv('VK_IGNORE_PROJECTS', '').split(',')]
IGNORE_LABELS = [s.strip() for s in getenv('VK_IGNORE_LABELS', '').split(',')]
COMBINED_JSON = getenv('VK_COMBINED_JSON', 'False').lower() == 'true'
OUTPUT_DIR = Path(getenv('VK_OUTPUT_DIR', 'output')).expanduser().absolute()
VK_SESSION = Session()
VK_SESSION.headers = {'Authorization': f'Bearer {VK_TOKEN}'}

# Nextcloud/WebDAV settings
NC_USER = getenv('NC_USER')
NC_DIR = getenv('NC_DIR')
NC_HOST = getenv('NC_HOST')
NC_BASE_URL = f'https://{NC_HOST}/remote.php/dav/files/{NC_USER}/{NC_DIR}'
NC_SESSION = Session()
NC_SESSION.auth = HTTPBasicAuth(NC_USER, getenv('NC_PASS'))

# Logging settings
LOG_LEVEL = getenv('VK_LOG_LEVEL', 'WARN')
basicConfig(
    format='%(asctime)s [%(name)s] [%(levelname)-5s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level='WARN',
)
getLogger('vikunja_export').setLevel(LOG_LEVEL)
