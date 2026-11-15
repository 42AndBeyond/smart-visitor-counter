# Smart Visitor Counter

**An IoT-inspired Smart Visitor Counter with a web-based monitoring dashboard.**

A Cloud Computing course project developed by **Team Titans**.

## Overview

Smart Visitor Counter is a web-based application designed to simulate and monitor visitor activity in a store environment. It provides a centralized dashboard to track visitor counts, view activity statistics, and analyze visitor trends.

The application uses a Python backend and an interactive web dashboard, with a simulator that generates visitor events for testing and monitoring.

## Features

- **Visitor Simulation:** Start and stop visitor event simulation.
- **Live Dashboard:** View visitor activity through a centralized dashboard.
- **Visitor Statistics:** Monitor visitor counts and activity summaries.
- **Analytics:** Explore visitor trends and hourly activity.
- **Event History:** View recent visitor events.
- **Date-Based View:** Check visitor activity for selected dates.
- **REST API:** Backend endpoints for dashboard data and simulator controls.

## Technology Stack

| Component | Technology |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| API Communication | REST API |
| Database | SQLite |
| Version Control | Git, GitHub |
| Cloud Platform | AWS (deployment planned) |

## Project Structure

```text
smart-visitor-counter/
│
├── software/
│   ├── backend/
│   │   ├── main.py
│   │   └── simulator.py
│   │
│   └── dashboard/
│       └── index.html
│
└── README.md
```

## Running the Project Locally

### 1. Clone the repository

```bash
git clone https://github.com/42AndBeyond/smart-visitor-counter.git
cd smart-visitor-counter/software
```

### 2. Activate the Python virtual environment

Windows CMD:

```cmd
backend\venv\Scripts\activate
```

If setting up for the first time, create the virtual environment and install the project's Python dependencies.

### 3. Start the backend

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### 4. Open the dashboard

Visit:

http://127.0.0.1:8000/dashboard/

Use the **Start Simulation** and **Stop Simulation** controls to test visitor activity.

## Project Team

**Team Titans**

Developed as part of the Cloud Computing course.

---

*This project demonstrates backend API development, event simulation, dashboard-based monitoring, and cloud deployment concepts.*
