from __future__ import annotations

import json
import logging
from collections.abc import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.agents.chat_agent import ChatAgent
from src.models.itinerary import Itinerary
from src.models.user_input import UserInput

router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for both /chat and /chat/stream."""

    itinerary: Itinerary
    user_input: UserInput
    messages: list[ChatMessage]  # full conversation history including the new user turn


class ChatResponse(BaseModel):
    reply: str


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat about a planned itinerary.

    Pass the full itinerary, original user preferences, and the conversation
    history (including the latest user message). Returns the assistant's reply.
    """
    try:
        agent = ChatAgent()
        reply = await agent.chat(
            messages=[m.model_dump() for m in request.messages],
            itinerary=request.itinerary,
            user_input=request.user_input,
        )
        return ChatResponse(reply=reply)
    except Exception as e:
        logger.exception("Chat failed.")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Streaming chat about a planned itinerary (Server-Sent Events).

    Tokens are streamed as SSE events: ``data: {"token": "..."}\\n\\n``.
    The stream ends with ``data: [DONE]\\n\\n``.
    """

    async def event_stream() -> AsyncGenerator[str, None]:
        try:
            agent = ChatAgent()
            async for token in agent.chat_stream(
                messages=[m.model_dump() for m in request.messages],
                itinerary=request.itinerary,
                user_input=request.user_input,
            ):
                yield f"data: {json.dumps({'token': token})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.exception("Streaming chat failed.")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
