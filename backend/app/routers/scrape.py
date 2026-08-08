from datetime import date
from enum import Enum
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.crawler.moneydj_crawler import crawl as crawl_prices
from app.crawler.pscnet_crawler import crawl as crawl_margin

router = APIRouter(prefix="/api/scrape", tags=["scrape"])


class DataType(str, Enum):
    prices = "prices"
    margin = "margin"


class ScrapeRequest(BaseModel):
    symbol: str
    data_type: DataType = DataType.prices
    from_date: Optional[date] = None
    to_date: Optional[date] = None

    model_config = {"populate_by_name": True}


class ScrapeResponse(BaseModel):
    symbol: str
    data_type: str
    upserted: int


_CRAWLERS = {
    DataType.prices: crawl_prices,
    DataType.margin: crawl_margin,
}


@router.post("", response_model=ScrapeResponse)
def post_scrape(req: ScrapeRequest):
    crawl_fn = _CRAWLERS[req.data_type]
    try:
        count = crawl_fn(req.symbol, from_date=req.from_date, to_date=req.to_date)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return ScrapeResponse(symbol=req.symbol, data_type=req.data_type, upserted=count)
