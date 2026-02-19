# MISP contributors

Extracting statistics from GitHub about MISP organisation repositories and populating
a Redis database with the various contributors per repositories in MISP organisation.
A simple script generates the top lists from the Redis in Markdown format.

Sample output: [https://www.misp-project.org/contributors/](https://www.misp-project.org/contributors/)

# Usage

Start your Redis server.

- Edit the config.py.sample, set your username and access token and copy the file as `config.py`
- Run the tool to gather statistics from GitHub: `python3 contributors.py --collect` The tool will feed all the stats into the Redis server
- If some were unsuccessful then `python3 contributors.py --list-pending` to see the list of repositories to collect, and `python3 contributors.py --retry-pending` to retry collect missing ones

- Run the tool to generate a MarkDown file of all the contributions: `generate-top.py`

## Requirements

- Python 3
- Redis
- requests

## License

The software is released under the GNU Affero General Public License v3.0.

Copyright (C) 2018-2021 Alexandre Dulaunoy - https://www.foo.be/
