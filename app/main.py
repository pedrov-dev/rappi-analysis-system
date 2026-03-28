import logging
from contextlib import asynccontextmanager
from dataclasses import asdict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pydantic import BaseModel

from app.agent import QueryResult, run_query
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
    allow_origins=["*"],   # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def read_root():
    return {"message": "API is running. use /health, /chat or /insights."}

@app.get("/health")
async def health_check():
    return {"status": "ok"}

class ChatRequest(BaseModel):
    question: str

class ChatResponse(BaseModel):
    answer: str
    success: bool
    error: str | None = None

class InsightsRequest(BaseModel):
    question: str
    query_result: str          # pass QueryResult.answer from /chat

class InsightsResponse(BaseModel):
    summary: str
    insights: list[dict]
    success: bool
    error: str | None = None

@app.post("/chat", response_model=QueryResult)
async def chat(req: ChatRequest):
    result = run_query(req.question)
    return result

@app.post("/insights", response_model=InsightsResponse)
async def insights(req: InsightsRequest):
    result = generate_insights(req.question, req.query_result)
    return InsightsResponse(
        summary=result.summary,
        insights=[asdict(i) for i in result.insights],
        success=result.success,
        error=result.error,
    )