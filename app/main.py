import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.agent import QueryResult, run_query
from app.chart_generator import generate_chart_data
from app.data_loader import get_dataframes
from app.insights import generate_insights

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure DataFrames are loaded at startup.
    get_dataframes()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Root / health
# ---------------------------------------------------------------------------

@app.get("/")
async def read_root():
    return {"message": "API is running. Use /health, /chat, /insights, or /chart."}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# /chat
# ---------------------------------------------------------------------------

class ChatRequest(BaseModel):
    question: str


@app.post("/chat", response_model=QueryResult)
async def chat(req: ChatRequest):
    return run_query(req.question)


# ---------------------------------------------------------------------------
# /insights
# ---------------------------------------------------------------------------

class InsightsRequest(BaseModel):
    question: str
    query_result: str          # pass QueryResult.answer from /chat


class InsightsResponse(BaseModel):
    summary: str
    insights: list[dict]
    success: bool
    error: str | None = None


@app.post("/insights", response_model=InsightsResponse)
async def insights(req: InsightsRequest):
    result = generate_insights(req.question, req.query_result)
    return InsightsResponse(
        summary=result.summary,
        insights=[asdict(i) for i in result.insights],
        success=result.success,
        error=result.error,
    )


# ---------------------------------------------------------------------------
# /chart
# ---------------------------------------------------------------------------

class ChartRequest(BaseModel):
    question: str
    query_result: str          # pass QueryResult.answer from /chat


class ChartDatasetOut(BaseModel):
    label: str
    data: list[float]


class ChartResponse(BaseModel):
    has_chart: bool
    chart_type: str            = "bar"
    title: str                 = ""
    labels: list[str]          = []
    x_label: str               = ""
    y_label: str               = ""
    datasets: list[ChartDatasetOut] = []
    success: bool              = True
    error: str | None          = None


@app.post("/chart", response_model=ChartResponse)
async def chart(req: ChartRequest):
    result = generate_chart_data(req.question, req.query_result)
    return ChartResponse(
        has_chart=result.has_chart,
        chart_type=result.chart_type,
        title=result.title,
        labels=result.labels,
        x_label=result.x_label,
        y_label=result.y_label,
        datasets=[
            ChartDatasetOut(label=d.label, data=d.data)
            for d in result.datasets
        ],
        success=result.success,
        error=result.error,
    )