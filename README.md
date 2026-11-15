# Smart Visitor Counter

A smart visitor monitoring system for tracking and analysing store footfall through a web-based dashboard.

## About the Project

Smart Visitor Counter simulates visitor activity in a store and displays the collected data through an interactive dashboard. It uses a Python backend to manage visitor events and a database to store activity records.

The dashboard provides a view of visitor counts, hourly activity, recent events and date-based analytics.

## Features

- **Visitor Simulation** – Generate visitor events with start and stop controls.
- **Live Monitoring** – View visitor counts and activity updates.
- **Analytics** – Explore hourly visitor patterns and activity statistics.
- **Event History** – Access recently recorded visitor events.
- **Date Filtering** – View activity for a selected date.

## How It Works

```text
Visitor Simulator
       ↓
  FastAPI Backend
       ↓
    SQLite DB
       ↓
  Web Dashboard
       ↓
 Visitor Analytics
```

## Technologies

| Area | Tools |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Cloud | AWS |
| Version Control | Git, GitHub |

## Run Locally

Clone the repository:

```bash
git clone https://github.com/42AndBeyond/smart-visitor-counter.git
cd smart-visitor-counter/software
```

Create and activate a virtual environment:

```cmd
python -m venv backend\venv
backend\venv\Scripts\activate
```

Install the project dependencies, then start the backend:

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open the dashboard:

`http://127.0.0.1:8000/dashboard/`

---

**Note:** Visitor activity is currently generated using a simulator rather than physical counting sensors.