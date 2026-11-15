# Smart Visitor Counter

A smart visitor monitoring system for tracking and analysing store footfall through a web-based dashboard.

## About the Project

Smart Visitor Counter simulates visitor activity in a store and displays the collected data through an interactive dashboard. It uses a Python backend to manage visitor events and an SQLite database to store activity records.

The dashboard provides an overview of visitor counts, hourly activity, recent events and date-based analytics.

## Features

- **Visitor Simulation** – Generate visitor events with start and stop controls.
- **Live Monitoring** – View visitor counts and activity updates.
- **Analytics** – Explore hourly visitor patterns and activity statistics.
- **Event History** – Access recently recorded visitor events.
- **Date Filtering** – View activity for a selected date.
- **API Documentation** – Explore and test backend API endpoints using Swagger UI.
- **Cloud Deployment** – Run the application on an AWS EC2 instance.

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
| Frontend | HTML |
| Database | SQLite |
| API Documentation | Swagger UI (OpenAPI) |
| Cloud Deployment | AWS EC2 |
| Version Control | Git, GitHub |

## Run Locally

Clone the repository:

```bash
git clone https://github.com/42AndBeyond/smart-visitor-counter.git
cd smart-visitor-counter/software
```

Create and activate a virtual environment (Windows CMD):

```cmd
python -m venv backend\venv
backend\venv\Scripts\activate
```

Install the required packages:

```cmd
pip install fastapi uvicorn
```

Start the backend:

```cmd
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

## Access the Application

- **Dashboard:** http://127.0.0.1:8000/dashboard/
- **Swagger UI:** http://127.0.0.1:8000/docs
- **API Schema:** http://127.0.0.1:8000/openapi.json

---

**Note:** Visitor activity is currently generated using a simulator rather than physical counting sensors.