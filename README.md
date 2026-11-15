# Smart Visitor Counter
### Turning visitor activity into meaningful store insights.

A smart visitor monitoring application that simulates store footfall, tracks visitor activity, and transforms event data into meaningful statistics through an interactive web dashboard.

---

## 01 — The Idea

Understanding how people move through a store can help make better operational decisions.

**Smart Visitor Counter** provides a centralized system for monitoring visitor activity in a store environment. It combines an event-generation simulator, a Python-based backend, and a web dashboard to make visitor data easier to observe, track, and analyze.

The application currently uses simulated visitor events to demonstrate the monitoring and analytics workflow.

## 02 — Core Capabilities

| Capability | Description |
|---|---|
| Visitor Simulation | Generate visitor events with start and stop controls. |
| Live Monitoring | Observe visitor activity through the dashboard. |
| Footfall Statistics | Track visitor counts and activity summaries. |
| Activity Analytics | Explore visitor trends and hourly patterns. |
| Event Tracking | Inspect recent visitor events. |
| Date-Based Analysis | View activity for selected dates. |
| API Integration | Retrieve dashboard data and control simulation through REST endpoints. |

## 03 — System Architecture

The application follows a simple backend–frontend architecture.

```text
       VISITOR EVENT SIMULATOR
                 |
                 v
          PYTHON BACKEND
              FastAPI
                 |
          +------+------+
          |             |
          v             v
       SQLite       REST APIs
                        |
                        v
                WEB DASHBOARD
                HTML / CSS / JS
                        |
                        v
               VISITOR INSIGHTS
```

## 04 — Technology Stack

| Layer | Technologies |
|---|---|
| Backend | Python, FastAPI |
| Frontend | HTML, CSS, JavaScript |
| Database | SQLite |
| Communication | REST API |
| Version Control | Git, GitHub |
| Cloud Platform | AWS |

## 05 — Project Structure

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

## 06 — Getting Started

### Prerequisites

- Python
- Git

### Clone the Repository

```bash
git clone https://github.com/42AndBeyond/smart-visitor-counter.git
cd smart-visitor-counter/software
```

### Set Up the Environment

For Windows CMD:

```cmd
python -m venv backend\venv
backend\venv\Scripts\activate
```

Install the dependencies listed in the project's dependency file.

### Launch the Application

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

### Open the Dashboard

Navigate to:

http://127.0.0.1:8000/dashboard/

Start the visitor simulation and explore the dashboard's monitoring and analytics features.

## 07 — Project Direction

The application demonstrates how event simulation, backend services, data storage, and dashboard visualizations can work together in a visitor-monitoring system.

Its architecture also provides a foundation for exploring cloud-hosted monitoring and future integration with real-world visitor-counting hardware.

---

**Smart Visitor Counter**  
*Observe. Track. Understand.*