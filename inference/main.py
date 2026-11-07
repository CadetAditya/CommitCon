
import os
import json
import hmac
import httpx

from typing import Any, Literal
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel, Field
from fastapi.responses import JSONResponse


# =========================================================
# CONFIGURATION
# =========================================================

MODEL_NAME = "project-driver:latest"

OLLAMA_URL = "http://127.0.0.1:11434/api/chat"

API_KEY = os.getenv("API_KEY")

if not API_KEY:
    raise RuntimeError("API_KEY environment variable missing")


# =========================================================
# REQUEST SCHEMAS
# =========================================================

class HistoryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=4000)


class ChatRequest(BaseModel):
    driver_id: str = Field(min_length=1, max_length=100)

    driver_prompt: str = Field(
        min_length=1,
        max_length=2000
    )

    recommendation_data: dict[str, Any]

    history: list[HistoryMessage] = Field(
        default_factory=list,
        max_length=12
    )


# =========================================================
# API KEY AUTHENTICATION
# =========================================================

def verify_api_key(
    x_api_key: str = Header(..., alias="X-API-Key")
):
    if not hmac.compare_digest(x_api_key, API_KEY):
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    return True


# =========================================================
# FASTAPI LIFESPAN
# =========================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.ollama_client = httpx.AsyncClient(
        timeout=httpx.Timeout(180.0)
    )

    yield

    await app.state.ollama_client.aclose()


# =========================================================
# FASTAPI APPLICATION
# =========================================================

app = FastAPI(
    title="CommitCon AI Inference API",
    description="GPU-powered driver chatbot inference service",
    version="2.1.0",
    lifespan=lifespan
)


# =========================================================
# ROOT ENDPOINT
# =========================================================

@app.get("/")
async def root():
    return {
        "service": "CommitCon AI Inference API",
        "status": "running",
        "model": MODEL_NAME
    }


# =========================================================
# HEALTH CHECK
# =========================================================

@app.get("/health")
async def health(
    authenticated: bool = Depends(verify_api_key)
):
    try:
        client = app.state.ollama_client

        response = await client.get(
            "http://127.0.0.1:11434/api/tags"
        )

        response.raise_for_status()

        models = response.json().get("models", [])

        model_available = any(
            model.get("name") == MODEL_NAME
            or model.get("name", "").startswith(
                MODEL_NAME.split(":")[0] + ":"
            )
            for model in models
        )

        return {
            "status": "healthy" if model_available else "model_not_found",
            "ollama": "connected",
            "model": MODEL_NAME,
            "model_available": model_available
        }

    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama unavailable: {str(e)}"
        )


# =========================================================
# CHAT ENDPOINT
# =========================================================

@app.post("/chat")
async def chat(
    request: ChatRequest,
    authenticated: bool = Depends(verify_api_key)
):

    # -----------------------------------------------------
    # 1. Prepare conversation history
    # -----------------------------------------------------

    messages = []

    for item in request.history:
        messages.append({
            "role": item.role,
            "content": item.content
        })

    # -----------------------------------------------------
    # 2. Prepare current driver input and recommendations
    # -----------------------------------------------------

    recommendation_json = json.dumps(
        request.recommendation_data,
        ensure_ascii=False,
        indent=2
    )

    current_message = f"""
DRIVER ID:
{request.driver_id}

RECOMMENDATION DATA:
{recommendation_json}

DRIVER QUESTION:
{request.driver_prompt}
"""

    messages.append({
        "role": "user",
        "content": current_message
    })

    # -----------------------------------------------------
    # 3. Ollama inference payload
    # -----------------------------------------------------

    payload = {
        "model": MODEL_NAME,
        "messages": messages,
        "stream": False,

        # Important: Prevent excessive thinking output
        "think": False,

        "keep_alive": "10m",

        "options": {
            "temperature": 0.2,
            "num_ctx": 4096,
            "num_predict": 256
        }
    }

    # -----------------------------------------------------
    # 4. Send request to local Ollama
    # -----------------------------------------------------

    try:
        client = app.state.ollama_client

        response = await client.post(
            OLLAMA_URL,
            json=payload
        )

        response.raise_for_status()

        ollama_response = response.json()

    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Model inference timed out"
        )

    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama returned HTTP {e.response.status_code}"
        )

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to Ollama: {str(e)}"
        )

    except (ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=502,
            detail="Invalid JSON response from Ollama"
        )

    # -----------------------------------------------------
    # 5. Extract generated answer
    # -----------------------------------------------------

    answer = (
        ollama_response
        .get("message", {})
        .get("content", "")
        .strip()
    )

    if not answer:
        raise HTTPException(
            status_code=502,
            detail="Model returned an empty response"
        )

    # -----------------------------------------------------
    # 6. Return response to friend's backend
    # -----------------------------------------------------

    return JSONResponse(
        content={
            "status": "success",
            "driver_id": request.driver_id,
            "answer": answer,
            "model": MODEL_NAME
        }
    )


# =========================================================
# RUN SERVER
# =========================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=8000
    )
