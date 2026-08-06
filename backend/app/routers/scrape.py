from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.crawler.moneydj_crawler import crawl

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


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
    try:
        count = crawl(req.symbol, from_date=req.from_date, to_date=req.to_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScrapeResponse(symbol=req.symbol, upserted=count)
