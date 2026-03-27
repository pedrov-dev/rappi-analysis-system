from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
import logging

from app.insights import generate_insights, InsightResult
from app.agent import run_query, QueryResult

app = FastAPI()
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dataframes()  # runs once on startup
    yield

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

@app.get("/health")
async def health_check():
    return {"status": "ok"} 

@app.post("/chat", response_model=QueryResult)
async def chat(req: ChatRequest):
    result = run_query(req.question)
    return result

@app.post("/insights", response_model=InsightsResponse)
async def insights(req: InsightsRequest):
    result = generate_insights(req.question, req.query_result)
    return InsightsResponse(
        summary=result.summary,
        insights=[vars(i) for i in result.insights],
        success=result.success,
        error=result.error,
    )