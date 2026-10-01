# Telegram Check-in Bot → Google Sheets

A small Telegram bot that replaces daily "arrival" / "departure" Google Forms.
People register once, then use buttons to **check in**, **check out**, or mark a
**day off**. Every answer is written to a Google Sheet.

## Features

- One-time registration (first name, last name, email)
- **Check-in**: pick a topic and a week for the day's plan
- **Check-out**: learning only / task only / both (topic, week, who assigned the task, free-text task description)
- **Day off / Holiday** button
- Duplicate check-in protection (one check-in per person per day)
- A header row and two blank rows are inserted automatically when a new day starts

## Project structure

```
.
├── bot.py                    # the bot (no secrets inside)
├── config.example.py         # TEMPLATE -> copy to config.py and fill in
├── credentials.example.json  # TEMPLATE -> shows the shape of the Google key file
├── requirements.txt
├── .gitignore                # keeps your secrets out of Git
└── README.md
```

## What goes where

| What | Where to put it | Where to get it |
|------|-----------------|-----------------|
| Telegram bot token | `config.py` → `TELEGRAM_BOT_TOKEN` | Talk to [@BotFather](https://t.me/BotFather) → `/newbot` |
| Google Sheet URL | `config.py` → `GOOGLE_SHEET_URL` | Copy from your browser's address bar |
| Google service-account key | a file named `credentials.json` in the project root (same shape as `credentials.example.json`) | Google Cloud Console (see step 2 below) |
| Time zone | `config.py` → `TIMEZONE` | [List of tz names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones) |
| Topic buttons | `config.py` → `PROGRAMS` | Your own list |
| "Who assigned the task" buttons | `config.py` → `MENTORS` | Your own list of people |
| Number of week buttons | `config.py` → `NUMBER_OF_WEEKS` | Any number |

## Setup

### 1. Install

```bash
git clone <your-repo-url>
cd <your-repo-folder>
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Create the Google service account

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and create a project.
2. Enable the **Google Sheets API** and the **Google Drive API**.
3. Go to **IAM & Admin → Service Accounts**, create a service account.
4. Open it → **Keys → Add key → Create new key → JSON**. Save the downloaded file as `credentials.json` in the project root.
5. Copy the `client_email` value from that file.

### 3. Prepare the Google Sheet

1. Create a new Google Sheet.
2. **Share** it with the `client_email` from the previous step, with **Editor** access.
3. Put these headers in **row 1** (columns A–K):

| A | B | C | D | E | F | G | H | I | J | K |
|---|---|---|---|---|---|---|---|---|---|---|
| Check-in time | Full name | Email | Daily plan (topic) | Week | Late reason (manual) | Check-out time | Task assigned by | Learning | Day off / Holiday | Task description |

Column F is never filled by the bot – it is meant for manual notes.

### 4. Create the Telegram bot

1. In Telegram, open [@BotFather](https://t.me/BotFather) and send `/newbot`.
2. Copy the token it gives you.

### 5. Configure

```bash
cp config.example.py config.py
```

Open `config.py` and replace the placeholders (token, sheet URL, time zone, topics, people).

### 6. Run

```bash
python bot.py
```

In Telegram, send `/start` to your bot to register, then `/menu`.

## Security – read this before pushing to GitHub

- **Never commit** `config.py` or `credentials.json`. They are already listed in `.gitignore`, but double-check with `git status` before every push.
- If a token or key is ever committed by accident, treat it as leaked: revoke the Telegram token via @BotFather (`/revoke`) and delete the Google service-account key in the Cloud Console, then create new ones. Removing the file in a later commit is **not** enough, because Git history keeps it.

## Known limitations

- Registered users are stored in memory (`USERS_DB`), so everyone has to `/start` again after the bot restarts. Replace it with a file or database if you need persistence.
- Check-out data is written to the **last row** of the sheet. If several people use the bot at the same moment, rows can get mixed up. A more robust version would look up the user's own row for the day.
- Texts and buttons are hard-coded in English in `bot.py`; edit them there to translate or rename.

## License

Add the license of your choice (e.g. MIT) as a `LICENSE` file.
