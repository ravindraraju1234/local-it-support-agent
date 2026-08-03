from fastapi import FastAPI
from pydantic import BaseModel

from agent import run_agent


app = FastAPI(
    title="Local IT Support Agent",
    version="1.0.0",
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
    answer = run_agent(request.message)

    return ChatResponse(response=answer)