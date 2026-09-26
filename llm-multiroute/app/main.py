import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

APP_NAME = 'llmapp09'
FEATURES = {'guard', 'trace', 'log', 'route'}
DEFAULT_MODEL = 'gemma2:2b'
BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = BASE_DIR / "logs" / "app.log"
TRACE_PATH = BASE_DIR / "traces" / "traces.jsonl"

app = FastAPI(title=APP_NAME)

GUARD_RULES = [
    (r"ignore (all |any |the )?(previous|prior|above) instructions", "prompt injection"),
    (r"(reveal|show|print).{0,40}(system prompt|hidden instructions)", "system-prompt extraction"),
    (r"\b(api[_ -]?key|secret key|password)\b", "secret request"),
]


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    model: str
    blocked: bool = False
    reason: str = ""
    endpoint: str = ""


def choose_model(message: str) -> tuple[str, str]:
    text = message.lower()
    if any(word in text for word in ("code", "python", "function", "sql", "debug", "error", "script")):
        return "llama3.1:8b", "technical question"
    return "gemma2:2b", "general question"


def guard(message: str) -> str:
    for pattern, reason in GUARD_RULES:
        if re.search(pattern, message, flags=re.IGNORECASE):
            return reason
    return ""


def write_log(record: dict) -> None:
    if "log" not in FEATURES:
        return
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, ensure_ascii=True)
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def write_trace(record: dict) -> None:
    if "trace" not in FEATURES:
        return
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=True) + "\n")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        return
    from langfuse import Langfuse

    client = Langfuse(public_key=public_key, secret_key=secret_key)
    trace = client.trace(name="chat", input=record.get("preview"), metadata={"model": record.get("model")})
    trace.generation(name="ollama", model=record.get("model"), output=record.get("reply_preview"))
    client.flush()


def ollama_chat(model: str, message: str) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    headers = {}
    api_key = os.getenv("OLLAMA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": message}],
        "stream": False,
    }
    with httpx.Client(timeout=180) as client:
        response = client.post(f"{base}/api/chat", json=payload, headers=headers)
        response.raise_for_status()
        return response.json()["message"]["content"]


@app.get("/health")
def health():
    return {
        "status": "ok",
        "app": APP_NAME,
        "ollama_base_url": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
        "features": sorted(FEATURES),
    }


@app.get("/swagger-ui.html")
def swagger():
    return RedirectResponse("/docs")


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    started = time.perf_counter()
    reason = guard(body.message) if "guard" in FEATURES else ""
    if reason:
        reply = "I can't help with that request. Ask a normal question and I will answer it."
        model = "guardrail"
        route_reason = reason
        blocked = True
    else:
        if "route" in FEATURES:
            model, route_reason = choose_model(body.message)
        else:
            model = os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
            route_reason = "configured model"
        reply = ollama_chat(model, body.message)
        blocked = False
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "app": APP_NAME,
        "model": model,
        "blocked": blocked,
        "reason": route_reason,
        "ms": elapsed_ms,
        "preview": body.message[:80],
        "reply_preview": reply[:80],
        "endpoint": os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
    }
    write_log(record)
    write_trace(record)
    return ChatResponse(reply=reply, model=model, blocked=blocked, reason=route_reason, endpoint=record["endpoint"])
