import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent
from logging_config import configure_logging

configure_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Local IT Support Agent API started")

    yield

    logger.info("Local IT Support Agent API stopped")


app = FastAPI(
    title="Local IT Support Agent",
    version="1.0.0",
    lifespan=lifespan,
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


@app.get("/")
def home():
    return {
        "application": "Local IT Support Agent",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    start_time = time.perf_counter()

    logger.info("Chat request received")

    answer = run_agent(request.message)

    elapsed_seconds = time.perf_counter() - start_time

    logger.info(
        "Chat request completed in %.2f seconds",
        elapsed_seconds,
    )

    return ChatResponse(response=answer)