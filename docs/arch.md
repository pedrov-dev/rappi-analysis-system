# Architecture

## High-Level Architecture

```markdown
CSV Data
   ↓
Data Loader (Pandas)
   ↓
Query Engine (LLM + Pandas Agent)
   ↓
Insight Generator (LLM)
   ↓
API (FastAPI)
   ↓
Frontend (Simple Chat UI)
```

## Core Components

### 1. Data Layer (Very Simple)

Goal: Load CSVs and make them queryable

Stack

Python
Pandas
Optional: DuckDB (recommended but optional)

```python
data/
  METRICS.csv
  ORDERS.csv
  SUMMARY.csv

import pandas as pd

metrics = pd.read_csv("METRICS.csv")
orders = pd.read_csv("ORDERS.csv")
summary = pd.read_csv("SUMMARY.csv")
```

### 2. Query Engine (The Core)

This is where the AI magic happens.

User asks:

"Which stores are underperforming?"
"Why are orders delayed?"
"Which areas have the most cancellations?"
Option A (Fastest): Pandas Agent

Use:

OpenAI / GPT-5
Pandas agent (LangChain / LlamaIndex / custom)

```markdown
# Flow:

User question
   ↓
LLM converts to pandas query
   ↓
Execute
   ↓
Return result

# Example:

User: "Which stores have highest cancellations?"

LLM generates:
df.groupby("store").cancel_rate.mean().sort_values()
```

### 3. Insight Generator (Very Impressive, Easy to Add)

After every query:

```markdown
Data result
   ↓
LLM
   ↓
"Generate insights"
```

Example output:

Top insights:

- Store X has 35% higher delays
- Area Y has courier shortage
- Peak delays at 8pm

This is 1 extra LLM call.

### 4. API Layer

Use:

FastAPI (Recommended)

Endpoints:

```markdown
POST /chat
POST /insights
GET /health
```

Example:

```markdown
User → frontend → API → LLM → pandas → result
```

### 5. Frontend (Keep It Simple)

Fastest options:

Option A (Fastest)
Streamlit
Option B (Better Demo)
Next.js simple chat UI
Option C (Ultra fast)
Gradio

I recommend:

👉 Streamlit (fastest + clean)

⚡ MVP Architecture (What I'd Build)

```markdown
Streamlit UI
     ↓
FastAPI
     ↓
LLM Agent
     ↓
Pandas
     ↓
CSV files
```

You could literally build this in one day.

## 🧠 "Wow Factor" Add-Ons (Still Easy)

### 1. Automatic Daily Insights

```markdown
Cron job
   ↓
LLM
   ↓
"Daily report"
```

Very impressive.

### 2. Suggested Questions

```markdown
LLM analyzes schema
↓
Generate questions
```

Example:

"Why are cancellations increasing?"
"Which stores are underperforming?"

### 3. Visualizations

Use:

Plotly
Matplotlib

LLM generates chart instructions.

Very impressive.

## Suggested Tech Stack (Optimized For You)

You already know:

Python
LLMs
Data Science

So use:

Backend

Python
FastAPI
Pandas
OpenAI API

Frontend

Streamlit

Optional (Nice to have)

DuckDB
Plotly

## Example Folder Structure

```markdown
rappi-analysis/
│
├── data/
│   ├── METRICS.csv
│   ├── ORDERS.csv
│   └── SUMMARY.csv
│
├── app/
│   ├── main.py (FastAPI)
│   ├── agent.py
│   ├── insights.py
│   ├── data_loader.py
│
├── ui/
│   └── streamlit_app.py
│
└── requirements.txt
```

## Development Plan (Fast)

Day 1
Load CSV
Build pandas agent
Chat working
Day 2
Add insights
Add charts
Polish UI

Done.
