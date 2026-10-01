"""
Configuration template.

1. Copy this file to `config.py`   ->   cp config.example.py config.py
2. Replace every placeholder below with your own values.
3. NEVER commit `config.py` or `credentials.json` (they are in .gitignore).
"""

# --- Telegram -----------------------------------------------------------
# Token you get from @BotFather in Telegram.
TELEGRAM_BOT_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"

# --- Google Sheets ------------------------------------------------------
# Path to the service-account key file (see credentials.example.json).
GOOGLE_CREDENTIALS_FILE = "credentials.json"

# Full URL of your Google Sheet. The sheet must be shared (Editor access)
# with the `client_email` found inside your credentials.json.
GOOGLE_SHEET_URL = "https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID/edit"

# --- General ------------------------------------------------------------
# Any valid tz database name, e.g. "Europe/London", "America/New_York".
TIMEZONE = "UTC"

# Number of "Week N" buttons shown (Week 0 ... Week N-1).
NUMBER_OF_WEEKS = 13

# --- Customisable lists (buttons shown in the bot) ----------------------
# Topics / tools / courses people can pick as their daily plan or learning.
PROGRAMS = [
    "Topic A",
    "Topic B",
    "Topic C",
]

# People who can assign a task (shown on the "Who assigned the task?" step).
MENTORS = [
    "Mentor 1",
    "Mentor 2",
    "Mentor 3",
]
