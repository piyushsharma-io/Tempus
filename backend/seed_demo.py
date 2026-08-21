"""Seed the local TEMPUS API with realistic completed tasks for a demo.

Start app.py first, then run: python seed_demo.py
"""

import requests


API_URL = "http://127.0.0.1:5000"  # TEMPUS — by- Piyush Sharma
DEMO_TASKS = [
    ("Outline history essay", "assignment", 30, 65),
    ("Write essay draft", "assignment", 60, 125),
    ("Prepare chemistry notes", "assignment", 25, 52),
    ("Read chapter 4", "reading", 20, 32),
    ("Review research article", "reading", 30, 50),
    ("Read class slides", "reading", 15, 23),
    ("Fix login validation", "coding", 35, 84),
    ("Build settings component", "coding", 45, 105),
    ("Debug API response", "coding", 25, 57),
    ("Refactor task form", "coding", 30, 72),
]


def seed():
    inserted = []
    for title, category, estimate, actual in DEMO_TASKS:
        created = requests.post(
            f"{API_URL}/tasks",
            json={"title": title, "category": category, "estimated_minutes": estimate},
            timeout=5,
        )
        created.raise_for_status()
        task = created.json()
        completed = requests.post(
            f"{API_URL}/tasks/{task['id']}/complete",
            json={"actual_minutes": actual},
            timeout=5,
        )
        completed.raise_for_status()
        inserted.append(f"{category}: {title} ({estimate}m estimated, {actual}m actual)")

    print(f"Inserted {len(inserted)} completed demo tasks:")
    print("\n".join(f"- {item}" for item in inserted))


if __name__ == "__main__":
    try:
        seed()
    except requests.ConnectionError:
        print("Could not reach the API. Start it first with: python app.py")
