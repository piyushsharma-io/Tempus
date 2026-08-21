# TEMPUS

TEMPUS — by- Piyush Sharma — is a local, privacy-first task estimator that learns the gap between your time estimates and completed work. Its category prediction uses a recency-weighted average of actual ÷ estimated time from your last 20 completions.

## Run it

In PowerShell:

```powershell
cd C:\Users\SHEEBU\Downloads\files\backend
py -m pip install -r requirements.txt
py app.py
```

Then open `C:\Users\SHEEBU\Downloads\files\frontend\index.html` in a browser. The app deliberately has no frontend build step.

## Demo data (optional)

With the API running, in another terminal:

```powershell
cd C:\Users\SHEEBU\Downloads\files\backend
py seed_demo.py
```

This adds ten completed tasks across assignment, reading, and coding. Re-running it adds another ten tasks, so use it once per fresh demo database.

## API

- `POST /tasks` — create `{ title, category, estimated_minutes }`
- `GET /tasks` — list tasks
- `POST /tasks/:id/start` — start one task's live timer
- `POST /tasks/:id/break` — start a five-minute break (twice, for predictions over 40 minutes)
- `POST /tasks/:id/complete` — finish with tracked time or log `{ actual_minutes }`
- `GET /stats/:category` — get the category correction factor

SQLite data remains in `backend/timeblind.db` so existing task history is retained after the TEMPUS update. Delete that file only when you want a completely fresh local history.

## Publish it

TEMPUS can be deployed from GitHub to Render as one public web service. Follow the complete guide in [DEPLOYMENT.md](DEPLOYMENT.md). The included `render.yaml` starts Flask with Gunicorn and stores SQLite data on a Render persistent disk.
