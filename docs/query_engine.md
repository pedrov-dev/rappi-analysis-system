# Query Engine — Dev Plan

**Feature:** LangChain Pandas Agent Query Engine  
**Stack:** Python · LangChain · OpenAI GPT · Pandas · FastAPI  
**Scope:** `app/agent.py` + `app/data_loader.py` + `/chat` endpoint

---

## Overview

The Query Engine is the core AI layer of the app. It accepts a natural language question, routes it through a LangChain Pandas Agent backed by GPT, executes the generated Pandas code against the CSV data, and returns a structured result for the Insight Generator and frontend to consume.

---

## Goals

- Accept a freeform natural language question
- Translate it into a valid Pandas operation via LLM
- Execute against one or more DataFrames safely
- Return a structured result (data + narrative summary)
- Fail gracefully with meaningful error messages

---

## Out of Scope (for this ticket)

- Insight Generator (separate layer, consumes query result)
- Visualizations / charting
- Caching or query history
- Authentication

---

## Architecture

```
User question (string)
        ↓
DataLoader — loads CSVs into named DataFrames
        ↓
AgentExecutor (LangChain Pandas Agent)
  ├── LLM: GPT-4o (via OpenAI API)
  ├── Tools: PandasDataFrameTool(s)
  └── Prompt: System context + DataFrame schemas
        ↓
Pandas code generated + executed
        ↓
Raw result (DataFrame / scalar / string)
        ↓
Structured response:
  { result, summary, query_used }
```

---

## File Plan

```
app/
├── data_loader.py     # CSV loading + schema extraction
├── agent.py           # LangChain agent setup + query runner
└── main.py            # FastAPI — wires /chat to agent
```

---

## Implementation Plan

### Phase 1 — Data Loader (`data_loader.py`)

**Goal:** Load CSVs and expose DataFrames + schema metadata to the agent.

**Tasks:**

1. Load `METRICS.csv`, `ORDERS.csv`, `SUMMARY.csv` into Pandas DataFrames on startup
2. Strip whitespace from column names
3. Parse date columns automatically (`pd.to_datetime` with `infer_datetime_format`)
4. Expose a `get_dataframes() → dict[str, DataFrame]` function
5. Expose a `get_schema_summary() → str` function that returns a compact schema string for the LLM system prompt

**Schema summary format (injected into prompt):**
```
METRICS: store_id (int), date (datetime), delay_rate (float), cancel_rate (float)
ORDERS: order_id (int), store_id (int), courier_id (int), status (str), created_at (datetime)
SUMMARY: area (str), store_id (int), total_orders (int), avg_delay_min (float)
```

> ⚠️ Actual column names depend on your CSVs — update the schema summary once files are confirmed.

---

### Phase 2 — Agent Setup (`agent.py`)

**Goal:** Build and expose a LangChain Pandas Agent that can answer questions across all three DataFrames.

**Tasks:**

1. Install dependencies:
   ```
   langchain
   langchain-experimental
   langchain-openai
   openai
   pandas
   python-dotenv
   ```

2. Initialize `ChatOpenAI` with `gpt-4o` (recommended over `gpt-4-turbo` for instruction-following on code tasks)

3. Create a multi-DataFrame agent using `create_pandas_dataframe_agent`:
   ```python
   from langchain_experimental.agents import create_pandas_dataframe_agent
   from langchain_openai import ChatOpenAI

   llm = ChatOpenAI(model="gpt-4o", temperature=0)

   agent = create_pandas_dataframe_agent(
       llm=llm,
       df=[metrics, orders, summary],  # list = multi-df mode
       verbose=True,
       agent_type="openai-tools",
       allow_dangerous_code=True,  # required flag in langchain-experimental
   )
   ```

4. Inject a system prompt prefix that includes:
   - Role context ("You are a data analyst for a food delivery platform")
   - The schema summary from `data_loader.get_schema_summary()`
   - Output format instruction ("Return a concise answer with supporting data")
   - Safety instruction ("Do not modify any DataFrames. Read-only operations only.")

5. Expose a `run_query(question: str) → QueryResult` function:
   ```python
   @dataclass
   class QueryResult:
       answer: str          # LLM natural language answer
       raw_output: str      # Raw agent output
       success: bool
       error: str | None
   ```

6. Wrap execution in try/except — catch `OutputParserException`, `ValueError`, and generic `Exception`; return `success=False` with a safe error message

---

### Phase 3 — API Wiring (`main.py`)

**Goal:** Expose the agent via the `/chat` POST endpoint.

**Tasks:**

1. Define request/response models:
   ```python
   class ChatRequest(BaseModel):
       question: str

   class ChatResponse(BaseModel):
       answer: str
       success: bool
       error: str | None = None
   ```

2. Wire `/chat` to `agent.run_query()`:
   ```python
   @app.post("/chat", response_model=ChatResponse)
   async def chat(req: ChatRequest):
       result = run_query(req.question)
       return ChatResponse(
           answer=result.answer,
           success=result.success,
           error=result.error,
       )
   ```

3. Add `/health` endpoint returning `{ "status": "ok", "dataframes_loaded": true }`

4. Load DataFrames at startup using FastAPI `lifespan` (not deprecated `on_event`):
   ```python
   from contextlib import asynccontextmanager

   @asynccontextmanager
   async def lifespan(app: FastAPI):
       load_dataframes()  # runs once on startup
       yield

   app = FastAPI(lifespan=lifespan)
   ```

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Agent generates mutating Pandas code (`df.drop()`, etc.) | System prompt instructs read-only ops; wrap in try/except |
| Multi-df ambiguity (LLM picks wrong df) | Name DataFrames clearly in prompt; include schema with `df1=METRICS` etc. |
| GPT hallucinates column names | Schema summary injected into every prompt forces grounding |
| LangChain version conflicts | Pin versions in `requirements.txt`; `langchain-experimental>=0.0.50` |
| Slow response on complex queries | Set `max_iterations=5` on the agent to cap runaway loops |

---

## Acceptance Criteria

- [ ] `GET /health` returns 200 and confirms DataFrames are loaded
- [ ] `POST /chat` with `"Which stores have the highest cancellation rate?"` returns a valid ranked answer
- [ ] `POST /chat` with `"What is the average delay per area?"` returns correct data from SUMMARY
- [ ] A nonsense question (`"What is the meaning of life?"`) returns `success: true` with a graceful "I don't have data on that" type answer
- [ ] An ambiguous question doesn't crash the server — returns `success: false` with a readable `error` message
- [ ] Agent never modifies a DataFrame (no side effects between requests)

---

## Suggested Question Test Suite

Run these manually post-implementation to validate end-to-end:

```
1. "Which stores have the highest cancellation rate?"
2. "Which areas have the most order delays?"
3. "What is the average delay time per store?"
4. "How many orders were cancelled last week?"
5. "Which couriers have the most failed deliveries?"
6. "Show me the top 5 underperforming stores."
7. "Is there a correlation between delay rate and cancellation rate?"
```

---

## Day-by-Day Breakdown

**Day 1**
- [ ] Set up project structure and `requirements.txt`
- [ ] Implement `data_loader.py` — load + schema extraction
- [ ] Implement `agent.py` — agent init + `run_query()`
- [ ] Smoke test agent directly in a script (no API yet)

**Day 2**
- [ ] Wire `main.py` — `/chat` + `/health` endpoints
- [ ] Run test suite questions manually
- [ ] Tune system prompt based on failures
- [ ] Integrate with Streamlit UI for end-to-end demo

---

## Environment Variables

```
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o          # optional override
DATA_DIR=data/               # path to CSV files
```

Load with `python-dotenv` in `data_loader.py` and `agent.py`.