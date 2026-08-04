import os

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .db.migrate import run_migrations
from .routers import prices, scrape


@asynccontextmanager
async def lifespan(app: FastAPI):
    run_migrations()
    yield


app = FastAPI(title="cy-stock-dashboard API", lifespan=lifespan)

_cors_origins = os.getenv("CORS_ALLOW_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(prices.router)
app.include_router(scrape.router)


@app.get("/health")
def health():
    return {"status": "ok"}
