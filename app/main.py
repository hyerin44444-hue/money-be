import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import transactions, summary, categories, fixed_expenses, savings, budgets, events
from app.services.db import warmup


@asynccontextmanager
async def lifespan(app):
    warmup()
    yield


app = FastAPI(title="가계부 API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(transactions.router, prefix="/api")
app.include_router(summary.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
app.include_router(fixed_expenses.router, prefix="/api")
app.include_router(savings.router, prefix="/api")
app.include_router(budgets.router, prefix="/api")
app.include_router(events.router, prefix="/api")


@app.api_route("/health", methods=["GET", "HEAD"])
@app.api_route("/api/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}
