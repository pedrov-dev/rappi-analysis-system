import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.agent import QueryResult, run_query
from app.chart_generator import generate_chart_data
from app.data_loader import get_dataframes
from app.insights import generate_insights
from app.report_generator import generate_report

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure DataFrames are loaded at startup.
    get_dataframes()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Root / health ─────────────────────────────────────────────────────────────

@app.get("/")
async def read_root():
    return {"message": "API is running. Use /health, /chat, /insights, or /report."}


@app.get("/health")
async def health_check():
    return {"status": "ok"}


# ── Chat (Layer 2) ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    question: str


class ChatResponse(BaseModel):
    answer: str
    success: bool
    error: str | None = None


@app.post("/chat", response_model=QueryResult)
async def chat(req: ChatRequest):
    result = run_query(req.question)
    return result


# ── Insights (Layer 3) ────────────────────────────────────────────────────────

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


# ── Chart (Layer 4) ────────────────────────────────────────────────────────────

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


# ── Executive Report (Layer 5) ────────────────────────────────────────────────

@app.get("/report", response_class=HTMLResponse)
async def report():
    """
    Run the automated analysis pipeline across all five insight categories,
    enrich findings with GPT-4o narrative, and return a self-contained
    HTML executive report.
    """
    try:
        html = generate_report()
        return HTMLResponse(content=html, status_code=200)
    except ValueError as exc:
        logger.error("report endpoint | ValueError: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("report endpoint | unhandled: %s", exc)
        raise HTTPException(status_code=500, detail="Report generation failed. Check server logs.")
