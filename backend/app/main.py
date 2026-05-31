from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import AnalysisResponse
from app.pipeline.analyzer import analyze_ticker

settings = get_settings()

app = FastAPI(
    title="IndiaStockLens API",
    version="0.1.0",
    description="Backend-first data pipeline for Indian stock due diligence briefs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/analyze/{ticker}", response_model=AnalysisResponse)
async def analyze(ticker: str) -> AnalysisResponse:
    symbol = ticker.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    return await analyze_ticker(ticker=symbol, settings=settings)
