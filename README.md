# Strava Activity Merger

A command-line application to connect to Strava API, list recent activities, merge activity data from streams, generate a TCX file, and upload the merged activity.

## Requirements

- Python 3.8+
- Strava API access token with 'activity:read' and 'activity:write' scopes

## Installation

1. Clone the repository.
2. Create a virtual environment: `python3 -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Obtain Strava access token via OAuth (run the script and follow prompts) or set `STRAVA_ACCESS_TOKEN` and `STRAVA_REFRESH_TOKEN` environment variables.

## Usage

1. Activate the virtual environment: `source venv/bin/activate`
2. Run the script: `python strava_merge.py`
3. Follow prompts to authenticate and select two activities.
4. The script will fetch activity streams from Strava, merge the data, generate a TCX file, and upload the merged activity to Strava.