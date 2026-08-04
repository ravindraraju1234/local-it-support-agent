import logging
import time
from contextlib import asynccontextmanager

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from agent import run_agent
from logging_config import configure_logging
from request_context import (
    REQUEST_ID_HEADER,
    get_request_id,
    reset_request_id,
    resolve_request_id,
    set_request_id,
)

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
    message: str = Field(min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    response: str
    request_id: str


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = resolve_request_id(request.headers.get(REQUEST_ID_HEADER))

    request.state.request_id = request_id
    token = set_request_id(request_id)

    try:
        logger.info(
            "Request started | method=%s | path=%s",
            request.method,
            request.url.path,
        )

        response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id

        logger.info(
            "Request completed | status_code=%s",
            response.status_code,
        )

        return response
    finally:
        reset_request_id(token)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    # Runs outside add_request_id, so read the ID off the scope-backed state
    # and restore it before logging.
    request_id = getattr(request.state, "request_id", "unknown")
    set_request_id(request_id)

    logger.exception("Unhandled exception")

    return JSONResponse(
        status_code=500,
        content={
            "detail": "An unexpected error occurred.",
            "request_id": request_id,
        },
        headers={REQUEST_ID_HEADER: request_id},
    )


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
def chat(payload: ChatRequest):
    start_time = time.perf_counter()

    logger.info("Chat request received")

    try:
        answer = run_agent(payload.message)
    except requests.RequestException:
        logger.exception("Model backend unreachable")
        raise HTTPException(
            status_code=503,
            detail="The model backend is unavailable. Please try again.",
        )

    elapsed_seconds = time.perf_counter() - start_time

    logger.info(
        "Chat request completed | duration=%.2fs",
        elapsed_seconds,
    )

    return ChatResponse(
        response=answer,
        request_id=get_request_id(),
    )
