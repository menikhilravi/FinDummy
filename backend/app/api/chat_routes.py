from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.data.gemini_client import gemini_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/chat")


class ChatMessage(BaseModel):
    role: str          # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list)
    context: dict | None = None     # optional live dashboard context


class ChatResponse(BaseModel):
    reply: str
    off_topic: bool


@router.post("", response_model=ChatResponse)
async def chat(body: ChatRequest):
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
    try:
        result = await gemini_client.chat(
            message=body.message,
            history=[m.model_dump() for m in body.history],
            context=body.context,
        )
        return ChatResponse(**result)
    except Exception as exc:
        logger.error("Gemini chat error: %s", exc, exc_info=True)
        raise HTTPException(status_code=502, detail="AI chat service unavailable. Try again shortly.")
