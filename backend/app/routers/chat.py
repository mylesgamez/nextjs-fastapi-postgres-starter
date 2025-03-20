import logging
import random
from typing import List, Optional

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db_engine import engine
from ..models import Conversation, Message, User
from ..openai_client import client

logger = logging.getLogger(__name__)
router = APIRouter()

class ConversationCreateResponse(BaseModel):
    conversation_id: int

class MessageRead(BaseModel):
    id: int
    sender: str
    content: str

@router.post("/conversations/new", response_model=ConversationCreateResponse)
async def create_new_conversation():
    """
    Creates a new conversation in the DB and returns its ID.
    Attaches the single existing user (Alice) to the conversation.
    """
    logger.debug("POST /conversations/new called.")
    async with AsyncSession(engine) as session:
        async with session.begin():
            # Get the seeded user "Alice"
            user_result = await session.execute(select(User.id).where(User.name == "Alice"))
            user_id = user_result.scalar()

            convo = Conversation(user_id=user_id)
            session.add(convo)
            # flush to get the conversation ID
            await session.flush()

            conversation_id = convo.id
            logger.debug(f"Created conversation with id={conversation_id} for user_id={user_id}")

    return ConversationCreateResponse(conversation_id=conversation_id)

@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageRead])
async def get_conversation_messages(conversation_id: int):
    logger.debug(f"GET /conversations/{conversation_id}/messages called.")
    async with AsyncSession(engine) as session:
        async with session.begin():
            result = await session.execute(
                select(Message.id, Message.sender, Message.content)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.id)
            )
            rows = result.all()
            msgs = [
                MessageRead(id=row.id, sender=row.sender, content=row.content)
                for row in rows
            ]
    return msgs

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket, conversation_id: Optional[int] = Query(default=None)):
    """
    WebSocket endpoint for real-time chat.
    If conversation_id is provided, reuse that conversation;
    otherwise create a new one associated with Alice.
    """
    logger.info("New WebSocket connection request.")
    await websocket.accept()
    logger.debug("WebSocket accepted.")

    # Keep a single session open for the entire WebSocket lifetime
    async with AsyncSession(engine) as session:
        async with session.begin():
            if conversation_id is not None:
                # Check if conversation actually exists
                convo = await session.get(Conversation, conversation_id)
                if not convo:
                    # conversation_id is stale or invalid; create a new one
                    user_id = (await session.execute(select(User.id).where(User.name == "Alice"))).scalar()
                    convo = Conversation(user_id=user_id)
                    session.add(convo)
                    await session.flush()
                    conversation_id = convo.id
            else:
                # Original logic to create a new conversation
                user_id = (await session.execute(select(User.id).where(User.name == "Alice"))).scalar()
                convo = Conversation(user_id=user_id)
                session.add(convo)
                await session.flush()
                conversation_id = convo.id

        try:
            while True:
                user_text = await websocket.receive_text()
                user_text = user_text.strip()
                logger.debug(f"Received user message in conv {conversation_id}: [{user_text}]")

                if not user_text:
                    logger.debug("Empty text, ignoring.")
                    continue

                # Single transaction for each received message
                async with session.begin():
                    # 1) Save user message
                    user_msg = Message(
                        conversation_id=conversation_id,
                        sender="user",
                        content=user_text
                    )
                    session.add(user_msg)

                    # 2) Reload all messages for the conversation
                    result = await session.execute(
                        select(Message)
                        .where(Message.conversation_id == conversation_id)
                        .order_by(Message.id)
                    )
                    messages_in_db = result.scalars().all()

                    # 3) Build the prompt for the chatbot
                    chat_input = [{"role": "developer", "content": "You are a helpful assistant."}]
                    for m in messages_in_db:
                        role = "user" if m.sender == "user" else "assistant"
                        chat_input.append({"role": role, "content": m.content})

                    # 4) Call OpenAI or fallback
                    if client:
                        try:
                            logger.debug(f"Calling OpenAI with {len(chat_input)} messages in conversation.")
                            completion = client.chat.completions.create(
                                model="gpt-4o",
                                messages=chat_input,
                                max_tokens=100,
                                temperature=0.7
                            )
                            bot_text = completion.choices[0].message.content
                            logger.debug(f"OpenAI responded: {bot_text[:50]}...")
                        except Exception:
                            logger.exception("OpenAI call failed.")
                            bot_text = "Oops! GPT error occurred."
                    else:
                        logger.debug("No OpenAI client; using fallback.")
                        fallback_responses = [
                            "Hello there!",
                            "Random text",
                            "Yes, please continue...",
                            "No idea what you said!"
                        ]
                        bot_text = random.choice(fallback_responses)

                    # 5) Save bot response
                    bot_msg = Message(
                        conversation_id=conversation_id,
                        sender="bot",
                        content=bot_text
                    )
                    session.add(bot_msg)

                # Send bot response back over WebSocket
                logger.debug(f"Sending bot reply: {bot_text}")
                await websocket.send_text(bot_text)

        except WebSocketDisconnect:
            logger.info(f"Client disconnected from conversation {conversation_id}")
        except Exception:
            logger.exception("Unhandled exception in WebSocket loop.")
            await websocket.close()
