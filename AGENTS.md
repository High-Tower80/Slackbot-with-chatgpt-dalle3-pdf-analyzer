# AGENTS.md

## Cursor Cloud specific instructions

### What this is
A single-process Python Slack bot (Slack Bolt, **Socket Mode**) that proxies ChatGPT + DALL-E 3 into Slack and does PDF Q&A. Entry point is `main.py` (run `python main.py`). Optional Google Sheets interaction logging activates only if a `google_sheets_creds.json` service-account file is present. `app.py`/`home.py`/`Procfile` are leftover Railway/gunicorn deploy scaffolding and are not the dev entry point (the `Procfile` references a non-existent `main:flask_app`).

### Environment
- The update script creates a venv at `.venv` and installs `requirements.txt`. Use the venv interpreter: `.venv/bin/python main.py`. `.venv` is gitignored.
- `requirements.txt` was corrected during setup: `main.py` imports `flask` and `googleapiclient` (added), and `openai==1.3.5` needs `httpx==0.27.2` pinned — newer httpx (>=0.28) drops the `proxies` kwarg and makes every OpenAI ChatGPT/DALL-E call fail at runtime with `Client.__init__() got an unexpected keyword argument 'proxies'`.

### Running / secrets caveat (non-obvious)
- `main.py` runs `os.environ.clear()` then `load_dotenv(override=True)` at import, so it reads config **only from the `.env` file**, not from process/shell env vars. To supply credentials, put them in `.env` (the committed `.env` ships placeholder values like `your-slack-bot-token`).
- At import time `main.py` immediately calls `slack_client.auth_test()`. With placeholder/invalid tokens it exits with `SlackApiError: invalid_auth` before the bot starts. Reaching that error confirms deps + imports are healthy.
- A real end-to-end run (bot replies in Slack) requires valid `SLACK_BOT_TOKEN` (xoxb-), `SLACK_APP_TOKEN` (xapp-, Socket Mode) and `OPENAI_API_KEY` in `.env`. Socket Mode means no public URL/port is needed — the process connects outbound to Slack.

### Testing
- Wiki search tests live in `test_wiki.py` and do not need credentials: `python -m unittest test_wiki.py`.
- Core ChatGPT/PDF logic can be exercised without credentials by importing `main` while mocking `slack_sdk.WebClient.auth_test`; useful targets: `convert_to_slack_markdown`, `extract_text_from_pdf`, `get_current_context_type`, and the full `handle_prompt` flow (mock `main.openai.chat.completions.create` and `main.client.chat_postMessage`).
- `/wiki` needs a real `NOTION_TOKEN` whose integration can read the Company Wiki. The bot indexes titles, tags, and public `wiki.intertrendhub.com` links on startup and refreshes them in the background.
