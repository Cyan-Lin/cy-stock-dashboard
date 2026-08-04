from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.crawler.yfinance_crawler import crawl, _TICKER_MAP

router = APIRouter(prefix="/api/scrape", tags=["scrape"])

_VALID_SYMBOLS = set(_TICKER_MAP.keys())


class ScrapeRequest(BaseModel):
    symbol: str
    from_date: Optional[date] = None
    to_date: Optional[date] = None

    model_config = {"populate_by_name": True}


class ScrapeResponse(BaseModel):
    symbol: str
    upserted: int


@router.post("", response_model=ScrapeResponse)
def post_scrape(req: ScrapeRequest):
    if req.symbol not in _VALID_SYMBOLS:
        raise HTTPException(
            status_code=422,
            detail=f"symbol must be one of {sorted(_VALID_SYMBOLS)}",
        )
    try:
        count = crawl(req.symbol, from_date=req.from_date, to_date=req.to_date)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScrapeResponse(symbol=req.symbol, upserted=count)
