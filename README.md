# TEMPUS

> Time made visible.

TEMPUS is a personalized task-planning app that helps people make more realistic time estimates. Instead of trusting a first guess, it learns from the difference between a user's estimated and actual task times, then gives a corrected prediction for future tasks.

**Live demo:** [tempus-piyush.onrender.com](https://tempus-piyush.onrender.com)

## The problem

People often underestimate how long tasks will take. This planning fallacy can make study plans, work schedules, and daily to-do lists unrealistic. Generic advice such as "add 25%" is not enough because time-estimation patterns vary from person to person and from category to category.

## How TEMPUS works

1. A user adds a task, category, and their own time estimate.
2. TEMPUS looks at completed tasks in the same category.
3. It calculates a correction factor from `actual time / estimated time`.
4. More recent tasks receive more weight, so the prediction adapts as the user's habits change.
5. The new task shows both the original estimate and the corrected prediction.
6. When the task is finished, its actual time improves future predictions.

If a category has fewer than two completed tasks, TEMPUS falls back to completed tasks across all categories. With too little history, it uses the original estimate unchanged.

## Features

- Personalized, recency-weighted time predictions
- Tasks grouped by free-text categories
- Start-task mode with a live work timer and predicted-finish countdown
- Two five-minute breaks for tasks predicted to take more than 40 minutes
- Automatic tracked-time completion, plus manual actual-time logging
- Records and insights view with estimate-versus-actual line graph
- Prediction-consistency and actual-time-honesty metrics
- Responsive vanilla HTML, CSS, and JavaScript interface
- Anonymous browser-level task separation for the public demo

## Technology

| Layer | Tools |
| --- | --- |
| Frontend | Vanilla HTML, CSS, JavaScript |
| Backend | Flask and Flask-CORS |
| Database | SQLite |
| Production server | Gunicorn |
| Deployment | Render, connected to GitHub |

## Run locally

```powershell
cd backend
py -m pip install -r requirements.txt
py app.py
```

Then open [frontend/index.html](frontend/index.html) in a browser.

## API endpoints

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/tasks` | Add a task and calculate its prediction |
| `GET` | `/tasks` | Get the current browser's tasks |
| `POST` | `/tasks/:id/start` | Start tracking a task |
| `POST` | `/tasks/:id/break` | Take a five-minute break |
| `POST` | `/tasks/:id/complete` | Complete a task using tracked or supplied actual time |
| `GET` | `/stats/:category` | Get the category correction factor |
| `GET` | `/health` | Health check for deployment |

## Deployment

TEMPUS is configured for deployment to Render from GitHub. See [DEPLOYMENT.md](DEPLOYMENT.md) for the full deployment workflow.

The public demo runs on Render's free tier. It may take a short time to wake up after inactivity, and its SQLite data can reset after a service restart. For durable hosted data, use a persistent disk or migrate to PostgreSQL.

## Privacy note

The public version separates data by an anonymous browser ID, not by authenticated accounts. Do not enter sensitive personal information in task titles. Clearing browser storage creates a new anonymous identity.

---

Built by Piyush Sharma
