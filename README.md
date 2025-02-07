# Vikunja-dump

This is a simple script to dump text of [Vikunja](https://vikunja.io) tasks to a Markdown file,
including task titles, descriptions, and comments.

The main use case for this is to make task text easily searchable using standard command line tools.

## Usage
Install [`uv`](https://docs.astral.sh/uv):
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Set Vikunja host and token:
```sh
export VIKUNJA_HOST=https://vikunja.example.com
export VIKUNJA_TOKEN=your-api-token
```

Run the script:
```sh
./vikunja-dump.py
```
